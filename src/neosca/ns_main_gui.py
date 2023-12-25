#!/usr/bin/env python3

import gc
import glob
import os
import os.path as os_path
import re
import subprocess
import sys
from typing import Generator, List, Set

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QAction, QCursor, QIcon, QStandardItem
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSystemTrayIcon,
    QTableView,
    QTabWidget,
    QWidget,
)

from neosca import ICON_PATH, QSS_PATH
from neosca.ns_about import __title__, __version__
from neosca.ns_io import Ns_IO
from neosca.ns_lca.ns_lca import Ns_LCA
from neosca.ns_platform_info import IS_MAC
from neosca.ns_qss import Ns_QSS
from neosca.ns_sca.structure_counter import StructureCounter
from neosca.ns_settings.ns_dialog_settings import Ns_Dialog_Settings
from neosca.ns_settings.ns_settings import Ns_Settings
from neosca.ns_settings.ns_settings_default import available_import_types
from neosca.ns_threads import Ns_Thread, Ns_Worker_LCA_Generate_Table, Ns_Worker_SCA_Generate_Table
from neosca.ns_widgets.ns_delegates import Ns_Delegate_SCA
from neosca.ns_widgets.ns_dialogs import (
    Ns_Dialog_Processing_With_Elapsed_Time,
    Ns_Dialog_Table,
    Ns_Dialog_Table_Acknowledgments,
    Ns_Dialog_TextEdit_Citing,
    Ns_Dialog_TextEdit_Err,
)
from neosca.ns_widgets.ns_tables import Ns_StandardItemModel, Ns_TableView
from neosca.ns_widgets.ns_widgets import Ns_MessageBox_Confirm


class Ns_Main_Gui(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(f"{__title__} {__version__}")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        qss = Ns_QSS.read_qss_file(QSS_PATH)
        qss += f"""\n* {{
         font-family: {Ns_Settings.value('Appearance/font-family')};
         font-size: {Ns_Settings.value('Appearance/font-size')}pt;
         }}"""
        self.setStyleSheet(qss)
        self.setup_menu()
        self.setup_worker()
        self.setup_main_window()
        self.resize_splitters()
        self.fix_macos_layout(self)
        self.setup_tray()

    # https://github.com/zealdocs/zeal/blob/9630cc94c155d87295e51b41fbab2bd5798f8229/src/libs/ui/mainwindow.cpp#L421C3-L433C24
    def setup_tray(self) -> None:
        menu_tray = QMenu(self)

        action_toggle = menu_tray.addAction("Minimize to Tray")
        action_toggle.triggered.connect(self.toggle_window)
        menu_tray.aboutToShow.connect(
            lambda: action_toggle.setText("Minimize to Tray" if self.isVisible() else f"Show {__title__}")
        )

        menu_tray.addSeparator()
        action_quit = menu_tray.addAction("Quit")
        action_quit.triggered.connect(self.close)

        self.trayicon = QSystemTrayIcon(QIcon(str(ICON_PATH)), self)
        self.trayicon.setContextMenu(menu_tray)
        self.trayicon.show()

    # https://github.com/zealdocs/zeal/blob/9630cc94c155d87295e51b41fbab2bd5798f8229/src/libs/ui/mainwindow.cpp#L447
    def bring_to_front(self) -> None:
        self.show()
        self.setWindowState(
            (self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive
        )
        self.raise_()
        self.activateWindow()

    # https://github.com/zealdocs/zeal/blob/9630cc94c155d87295e51b41fbab2bd5798f8229/src/libs/ui/mainwindow.cpp#L529
    def toggle_window(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.bring_to_front()

    # https://github.com/BLKSerene/Wordless/blob/fa743bcc2a366ec7a625edc4ed6cfc355b7cd22e/wordless/wl_main.py#L266
    def fix_macos_layout(self, parent):
        if not IS_MAC:
            return

        for widget in parent.children():
            if widget.children():
                self.fix_macos_layout(widget)
            else:
                if isinstance(widget, QWidget) and not isinstance(widget, QPushButton):
                    widget.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)

    def setup_menu(self):
        # File
        self.menu_file = QMenu("File", self.menuBar())
        action_open_file = QAction("Open File...", self.menu_file)
        action_open_file.setShortcut("CTRL+O")
        action_open_file.triggered.connect(self.menubar_file_open_file)
        action_open_folder = QAction("Open Folder...", self.menu_file)
        action_open_folder.setShortcut("CTRL+F")
        action_open_folder.triggered.connect(self.menubar_file_open_folder)
        # action_restart = QAction("Restart", self.menu_file)  # TODO remove this before releasing
        # action_restart.triggered.connect(self.menubar_file_restart)  # TODO remove this before releasing
        # action_restart.setShortcut("CTRL+R")  # TODO remove this before releasing
        action_quit = QAction("Quit", self.menu_file)
        action_quit.setShortcut("CTRL+Q")
        action_quit.triggered.connect(self.close)
        self.menu_file.addAction(action_open_file)
        self.menu_file.addAction(action_open_folder)
        self.menu_file.addSeparator()
        # self.menu_file.addAction(action_restart)
        self.menu_file.addAction(action_quit)
        # Edit
        self.menu_prefs = QMenu("Preferences", self.menuBar())
        action_settings = QAction("Settings...", self.menu_prefs)
        # TODO: remove this before releasing
        action_settings.setShortcut("CTRL+,")
        action_settings.triggered.connect(self.menubar_prefs_settings)
        action_increase_font_size = QAction("Increase Font Size", self.menu_prefs)
        action_increase_font_size.setShortcut("CTRL+=")
        action_increase_font_size.triggered.connect(self.menubar_prefs_increase_font_size)
        action_decrease_font_size = QAction("Decrease Font Size", self.menu_prefs)
        action_decrease_font_size.setShortcut("CTRL+-")
        action_decrease_font_size.triggered.connect(self.menubar_prefs_decrease_font_size)
        action_reset_layout = QAction("Reset Layouts", self.menu_prefs)
        action_reset_layout.triggered.connect(lambda: self.resize_splitters(is_reset=True))
        self.menu_prefs.addAction(action_settings)
        self.menu_prefs.addAction(action_increase_font_size)
        self.menu_prefs.addAction(action_decrease_font_size)
        self.menu_prefs.addAction(action_reset_layout)
        # Help
        self.menu_help = QMenu("Help", self.menuBar())
        action_citing = QAction("Citing", self.menu_help)
        action_citing.triggered.connect(self.menubar_help_citing)
        action_acks = QAction("Acknowledgments", self.menu_help)
        action_acks.triggered.connect(self.menubar_help_acks)
        self.menu_help.addAction(action_citing)
        self.menu_help.addAction(action_acks)

        self.menuBar().addMenu(self.menu_file)
        self.menuBar().addMenu(self.menu_prefs)
        self.menuBar().addMenu(self.menu_help)

    # Override
    def close(self) -> bool:
        if not Ns_Settings.value("Miscellaneous/dont-confirm-on-exit", type=bool) and any(
            (not model.is_empty() and not model.has_been_exported) for model in (self.model_sca, self.model_lca)
        ):
            checkbox_exit = QCheckBox("Don't confirm on exit")
            checkbox_exit.stateChanged.connect(
                lambda: Ns_Settings.setValue("Miscellaneous/dont-confirm-on-exit", checkbox_exit.isChecked())
            )
            messagebox = Ns_MessageBox_Confirm(
                self,
                f"Quit {__title__}",
                "<b>All unsaved data will be lost.</b> Do you really want to exit?",
                QMessageBox.Icon.Warning,
            )
            messagebox.setCheckBox(checkbox_exit)
            if not messagebox.exec():
                return False

        for splitter in (self.splitter_central_widget,):
            Ns_Settings.setValue(splitter.objectName(), splitter.saveState())
        Ns_Settings.sync()

        return super().close()

    def menubar_prefs_settings(self) -> None:
        attr = "dialog_settings"
        if hasattr(self, attr):
            getattr(self, attr).exec()
        else:
            dialog_settings = Ns_Dialog_Settings(self)
            setattr(self, attr, dialog_settings)
            dialog_settings.exec()

    def menubar_prefs_increase_font_size(self) -> None:
        key = "Appearance/font-size"
        point_size = Ns_Settings.value(key, type=int) + 1
        if point_size < Ns_Settings.value("Appearance/font-size-max", type=int):
            Ns_QSS.set_value(self, {"*": {"font-size": f"{point_size}pt"}})
            Ns_Settings.setValue(key, point_size)

    def menubar_prefs_decrease_font_size(self) -> None:
        key = "Appearance/font-size"
        point_size = Ns_Settings.value(key, type=int) - 1
        if point_size > Ns_Settings.value("Appearance/font-size-min", type=int):
            Ns_QSS.set_value(self, {"*": {"font-size": f"{point_size}pt"}})
            Ns_Settings.setValue(key, point_size)

    def menubar_help_citing(self) -> None:
        dialog_citing = Ns_Dialog_TextEdit_Citing(self)
        dialog_citing.exec()

    def menubar_help_acks(self) -> None:
        dialog_acks = Ns_Dialog_Table_Acknowledgments(self)
        dialog_acks.exec()

    def setup_tab_sca(self):
        self.button_generate_table_sca = QPushButton("Generate table")
        # self.button_generate_table_sca.setShortcut("CTRL+G")
        self.button_export_table_sca = QPushButton("Export table...")
        self.button_export_table_sca.setEnabled(False)
        # self.button_export_selected_cells = QPushButton("Export selected cells...")
        # self.button_export_selected_cells.setEnabled(False)
        self.button_export_matches_sca = QPushButton("Export matches...")
        self.button_export_matches_sca.setEnabled(False)
        self.button_clear_table_sca = QPushButton("Clear table")
        self.button_clear_table_sca.setEnabled(False)

        # TODO comment this out before releasing
        self.button_custom_func = QPushButton("Custom func")
        # TODO comment this out before releasing
        self.button_custom_func.clicked.connect(self.custom_func)

        self.model_sca = Ns_StandardItemModel(self)
        self.model_sca.setColumnCount(len(StructureCounter.DEFAULT_MEASURES))
        self.model_sca.setHorizontalHeaderLabels(StructureCounter.DEFAULT_MEASURES)
        self.model_sca.clear_data()
        self.tableview_sca = Ns_TableView(self, model=self.model_sca)
        self.tableview_sca.setItemDelegate(Ns_Delegate_SCA(None, self.styleSheet()))

        # Bind
        self.button_generate_table_sca.clicked.connect(self.ns_thread_sca_generate_table.start)
        self.button_export_table_sca.clicked.connect(
            lambda: self.tableview_sca.export_table("neosca_sca_results.xlsx")
        )
        self.button_export_matches_sca.clicked.connect(self.tableview_sca.export_matches)
        self.button_clear_table_sca.clicked.connect(lambda: self.model_sca.clear_data(confirm=True))
        self.model_sca.data_cleared.connect(
            lambda: self.button_generate_table_sca.setEnabled(True) if not self.model_file.is_empty() else None
        )
        self.model_sca.data_cleared.connect(lambda: self.button_export_table_sca.setEnabled(False))
        self.model_sca.data_cleared.connect(lambda: self.button_export_matches_sca.setEnabled(False))
        self.model_sca.data_cleared.connect(lambda: self.button_clear_table_sca.setEnabled(False))
        self.model_sca.data_updated.connect(lambda: self.button_export_table_sca.setEnabled(True))
        self.model_sca.data_updated.connect(lambda: self.button_export_matches_sca.setEnabled(True))
        self.model_sca.data_updated.connect(lambda: self.button_clear_table_sca.setEnabled(True))
        self.model_sca.data_updated.connect(lambda: self.button_generate_table_sca.setEnabled(False))

        self.widget_previewarea_sca = QWidget()
        self.layout_previewarea_sca = QGridLayout()
        self.widget_previewarea_sca.setLayout(self.layout_previewarea_sca)
        for btn_no, btn in enumerate(
            (
                self.button_generate_table_sca,
                self.button_export_table_sca,
                self.button_export_matches_sca,
                self.button_clear_table_sca,
                self.button_custom_func,
            ),
            start=1,
        ):
            self.layout_previewarea_sca.addWidget(btn, 1, btn_no - 1)
        self.layout_previewarea_sca.addWidget(self.tableview_sca, 0, 0, 1, btn_no)
        self.layout_previewarea_sca.setContentsMargins(0, 0, 0, 0)

    def custom_func(self):
        # import gc
        # import time
        #
        # from neosca.ns_sca.structure_counter import Structure, StructureCounter
        # counters =[]
        # ss = []
        # for o in gc.get_objects():
        #     if isinstance(o, StructureCounter):
        #         counters.append(o)
        #     elif isinstance(o, Structure):
        #         ss.append(o)
        # gc.collect()
        # filename = "{}.txt".format(time.strftime("%H-%M-%S"))
        # with open(filename, "w") as f:
        #     f.write("\n".join(str(o) for o in gc.get_objects()))
        breakpoint()

    def setup_tab_lca(self):
        self.button_generate_table_lca = QPushButton("Generate table")
        # self.button_generate_table_lca.setShortcut("CTRL+G")
        self.button_export_table_lca = QPushButton("Export table...")
        self.button_export_table_lca.setEnabled(False)
        # self.button_export_selected_cells = QPushButton("Export selected cells...")
        # self.button_export_selected_cells.setEnabled(False)
        self.button_clear_table_lca = QPushButton("Clear table")
        self.button_clear_table_lca.setEnabled(False)

        self.model_lca = Ns_StandardItemModel(self)
        self.model_lca.setColumnCount(len(Ns_LCA.FIELDNAMES) - 1)
        self.model_lca.setHorizontalHeaderLabels(Ns_LCA.FIELDNAMES[1:])
        self.model_lca.clear_data()
        self.tableview_lca = Ns_TableView(self, model=self.model_lca)
        # TODO: tableview_sca use custom delegate to only enable
        # clickable items, in which case a dialog will pop up to show matches.
        # Here when tableview_lca also use custom delegate, remember to
        # remove this line.
        self.tableview_lca.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Bind
        self.button_generate_table_lca.clicked.connect(self.ns_thread_lca_generate_table.start)
        self.button_export_table_lca.clicked.connect(
            lambda: self.tableview_lca.export_table("neosca_lca_results.xlsx")
        )
        self.button_clear_table_lca.clicked.connect(lambda: self.model_lca.clear_data(confirm=True))
        self.model_lca.data_cleared.connect(
            lambda: self.button_generate_table_lca.setEnabled(True) if not self.model_file.is_empty() else None
        )
        self.model_lca.data_cleared.connect(lambda: self.button_export_table_lca.setEnabled(False))
        self.model_lca.data_cleared.connect(lambda: self.button_clear_table_lca.setEnabled(False))
        self.model_lca.data_updated.connect(lambda: self.button_export_table_lca.setEnabled(True))
        self.model_lca.data_updated.connect(lambda: self.button_clear_table_lca.setEnabled(True))
        self.model_lca.data_updated.connect(lambda: self.button_generate_table_lca.setEnabled(False))

        self.widget_previewarea_lca = QWidget()
        self.layout_previewarea_lca = QGridLayout()
        self.widget_previewarea_lca.setLayout(self.layout_previewarea_lca)
        for btn_no, btn in enumerate(
            (
                self.button_generate_table_lca,
                self.button_export_table_lca,
                self.button_clear_table_lca,
            ),
            start=1,
        ):
            self.layout_previewarea_lca.addWidget(btn, 1, btn_no - 1)
        self.layout_previewarea_lca.addWidget(self.tableview_lca, 0, 0, 1, btn_no)
        self.layout_previewarea_lca.setContentsMargins(0, 0, 0, 0)

    def resize_splitters(self, is_reset: bool = False) -> None:
        for splitter in (self.splitter_central_widget,):
            key = splitter.objectName()
            if not is_reset and Ns_Settings.contains(key):
                splitter.restoreState(Ns_Settings.value(key))
            else:
                if splitter.orientation() == Qt.Orientation.Vertical:
                    total_size = splitter.size().height()
                else:
                    total_size = splitter.size().width()
                section_size = Ns_Settings.value(f"default-{key}", type=int)
                splitter.setSizes((total_size - section_size, section_size))

    def enable_button_generate_table(self, enabled: bool) -> None:
        self.button_generate_table_sca.setEnabled(enabled)
        self.button_generate_table_lca.setEnabled(enabled)

    def setup_tableview_file(self) -> None:
        self.model_file = Ns_StandardItemModel(self)
        self.model_file.setHorizontalHeaderLabels(("Name", "Path"))
        self.model_file.data_cleared.connect(lambda: self.enable_button_generate_table(False))
        self.model_file.data_updated.connect(lambda: self.enable_button_generate_table(True))
        self.model_file.clear_data()
        self.tableview_file = Ns_TableView(self, model=self.model_file, has_vertical_header=False)
        self.tableview_file.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableview_file.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tableview_file.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableview_file.setCornerButtonEnabled(True)
        # https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#PySide6.QtWidgets.PySide6.QtWidgets.QWidget.customContextMenuRequested
        self.menu_tableview_file = QMenu(self)
        self.action_tableview_file_remove = QAction("Remove", self.menu_tableview_file)
        self.action_tableview_file_remove.triggered.connect(self.remove_file_paths)
        self.menu_tableview_file.addAction(self.action_tableview_file_remove)
        self.tableview_file.customContextMenuRequested.connect(self.show_menu_for_tableview_file)

    def remove_file_paths(self) -> None:
        # https://stackoverflow.com/questions/5927499/how-to-get-selected-rows-in-qtableview
        indexes: List[QModelIndex] = self.tableview_file.selectionModel().selectedRows()
        # Remove rows from bottom to top, or otherwise lower row indexes will
        # change as upper rows are removed
        rownos = sorted((index.row() for index in indexes), reverse=True)
        for rowno in rownos:
            self.model_file.takeRow(rowno)
        if self.model_file.rowCount() == 0:
            self.model_file.clear_data()

    def show_menu_for_tableview_file(self) -> None:
        if not self.tableview_file.selectionModel().selectedRows():
            self.action_tableview_file_remove.setEnabled(False)
        else:
            self.action_tableview_file_remove.setEnabled(True)
        self.menu_tableview_file.exec(QCursor.pos())

    def add_file_paths(self, file_paths_to_add: List[str]) -> None:
        unique_file_paths_to_add: Set[str] = set(file_paths_to_add)
        already_added_file_paths: Set[str] = set(self.yield_added_file_paths())
        file_paths_dup: Set[str] = unique_file_paths_to_add & already_added_file_paths
        file_paths_unsupported: Set[str] = set(
            filter(lambda p: Ns_IO.suffix(p) not in Ns_IO.SUPPORTED_EXTENSIONS, file_paths_to_add)
        )
        file_paths_empty: Set[str] = set(filter(lambda p: not os_path.getsize(p), unique_file_paths_to_add))
        file_paths_ok: Set[str] = (
            unique_file_paths_to_add
            - already_added_file_paths
            - file_paths_dup
            - file_paths_unsupported
            - file_paths_empty
        )
        if file_paths_ok:
            self.model_file.remove_empty_rows()
            colno_name = 0
            # Has no duplicates
            already_added_file_names = list(self.model_file.yield_model_column(colno_name))
            for file_path in file_paths_ok:
                file_name = os_path.splitext(os_path.basename(file_path))[0]
                if file_name in already_added_file_names:
                    occurrence = 2
                    while f"{file_name} ({occurrence})" in already_added_file_names:
                        occurrence += 1
                    file_name = f"{file_name} ({occurrence})"
                already_added_file_names.append(file_name)
                rowno = self.model_file.rowCount()
                self.model_file.set_row_str(rowno, (file_name, file_path))
                self.model_file.data_updated.emit()

        if file_paths_dup or file_paths_unsupported or file_paths_empty:
            model_err_files = Ns_StandardItemModel(self)
            model_err_files.setHorizontalHeaderLabels(("Error Type", "File Path"))
            for reason, file_paths in (
                ("Duplicate file", file_paths_dup),
                ("Unsupported file type", file_paths_unsupported),
                ("Empty file", file_paths_empty),
            ):
                for file_path in file_paths:
                    model_err_files.appendRow((QStandardItem(reason), QStandardItem(file_path)))
            tableview_err_files = Ns_TableView(self, model=model_err_files, has_vertical_header=False)

            dialog = Ns_Dialog_Table(
                self,
                title="Error Adding Files",
                text="Failed to add the following files.",
                tableview=tableview_err_files,
                export_filename="neosca_error_files.xlsx",
            )
            dialog.exec()

    def setup_main_window(self):
        self.setup_tab_sca()
        self.setup_tab_lca()
        self.setup_tableview_file()

        self.tabwidget = QTabWidget()
        self.tabwidget.addTab(self.widget_previewarea_sca, "Syntactic Complexity Analyzer")
        self.tabwidget.addTab(self.widget_previewarea_lca, "Lexical Complexity Analyzer")
        self.splitter_central_widget = QSplitter(Qt.Orientation.Vertical)
        self.splitter_central_widget.setChildrenCollapsible(False)
        self.splitter_central_widget.addWidget(self.tabwidget)
        self.splitter_central_widget.addWidget(self.tableview_file)
        self.splitter_central_widget.setStretchFactor(0, 1)
        self.splitter_central_widget.setObjectName("splitter-file")
        self.setCentralWidget(self.splitter_central_widget)

    def sca_add_data(self, counter: StructureCounter, file_name: str, rowno: int) -> None:
        # Remove trailing rows
        self.model_sca.removeRows(rowno, self.model_sca.rowCount() - rowno)
        for colno in range(self.model_sca.columnCount()):
            sname = self.model_sca.horizontalHeaderItem(colno).text()

            value = counter.get_value(sname)
            value_str: str = str(value) if value is not None else ""
            item = QStandardItem(value_str)
            self.model_sca.set_item_num(rowno, colno, item)

            if matches := counter.get_matches(sname):
                item.setData(matches, Qt.ItemDataRole.UserRole)

        # from neosca.ns_sca.structure_counter import StructureCounter
        # print('='*80)
        # print("deleting counter")
        # for i in gc.get_objects():
        #     if isinstance(i, StructureCounter):
        #         print(i.ifile)
        #         print(id(i))
        #         print(sys.getrefcount(i))
        #         print(id(counter))
        #         print(sys.getrefcount(i))
        # else:
        #     print("Not found1")
        # del counter
        # gc.collect()
        # print('='*80)
        # for i in gc.get_objects():
        #     if isinstance(i, StructureCounter):
        #         print(i.ifile)
        #         print(sys.getrefcount(i))
        #         print(id(i))
        # else:
        #     print("Not found2")
        # print("deleted")
        self.model_sca.setVerticalHeaderItem(rowno, QStandardItem(file_name))
        self.model_sca.data_updated.emit()

    def setup_worker(self) -> None:
        self.dialog_processing = Ns_Dialog_Processing_With_Elapsed_Time(self)

        self.ns_worker_sca_generate_table = Ns_Worker_SCA_Generate_Table(main=self)
        self.ns_worker_sca_generate_table.counter_ready.connect(self.sca_add_data)
        self.ns_thread_sca_generate_table = Ns_Thread(self.ns_worker_sca_generate_table)
        self.ns_thread_sca_generate_table.started.connect(self.dialog_processing.exec)
        self.ns_thread_sca_generate_table.finished.connect(self.dialog_processing.accept)
        self.ns_thread_sca_generate_table.err_occurs.connect(
            lambda ex: Ns_Dialog_TextEdit_Err(self, ex=ex).exec()
        )

        self.ns_worker_lca_generate_table = Ns_Worker_LCA_Generate_Table(main=self)
        self.ns_thread_lca_generate_table = Ns_Thread(self.ns_worker_lca_generate_table)
        self.ns_thread_lca_generate_table.started.connect(self.dialog_processing.exec)
        self.ns_thread_lca_generate_table.finished.connect(self.dialog_processing.accept)
        self.ns_thread_lca_generate_table.err_occurs.connect(
            lambda ex: Ns_Dialog_TextEdit_Err(self, ex=ex).exec()
        )

    def yield_added_file_names(self) -> Generator[str, None, None]:
        colno_path = 0
        return self.model_file.yield_model_column(colno_path)

    def yield_added_file_paths(self) -> Generator[str, None, None]:
        colno_path = 1
        return self.model_file.yield_model_column(colno_path)

    def menubar_file_open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            caption="Open Folder", dir=Ns_Settings.value("Import/default-path")
        )
        if not folder_path:
            return

        file_paths_to_add = []
        for extension in Ns_IO.SUPPORTED_EXTENSIONS:
            file_paths_to_add.extend(glob.glob(os_path.join(folder_path, f"*.{extension}")))
        self.add_file_paths(file_paths_to_add)

    def menubar_file_open_file(self):
        file_paths_to_add, _ = QFileDialog.getOpenFileNames(
            parent=None,
            caption="Open Files",
            dir=Ns_Settings.value("Import/default-path"),
            filter=";;".join(available_import_types),
            selectedFilter=Ns_Settings.value("Import/default-type"),
        )
        if not file_paths_to_add:
            return
        self.add_file_paths(file_paths_to_add)

    def menubar_file_restart(self):
        self.trayicon.hide()
        self.close()
        command = [sys.executable, "-m", "neosca"]
        subprocess.call(command, env=os.environ.copy(), close_fds=False)
        sys.exit(0)


def main_gui():
    ui_scaling = Ns_Settings.value("Appearance/scaling")
    # https://github.com/BLKSerene/Wordless/blob/main/wordless/wl_main.py#L1238
    os.environ["QT_SCALE_FACTOR"] = re.sub(r"([0-9]{2})%$", r".\1", ui_scaling)
    ns_app = QApplication(sys.argv)
    ns_window = Ns_Main_Gui()
    ns_window.showMaximized()
    sys.exit(ns_app.exec())
