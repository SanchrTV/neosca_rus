#!/usr/bin/env python3

import json
import re
import sys
import traceback
from enum import Enum
from typing import List, Optional, Union

from PySide6.QtCore import (
    QElapsedTimer,
    QModelIndex,
    QPersistentModelIndex,
    QTime,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QIcon,
    Qt,
    QTextBlockFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QTextEdit,
)

from neosca import ACKS_PATH, CITING_PATH, ICON_PATH
from neosca.ns_about import __email__, __title__, __version__
from neosca.ns_widgets.ns_labels import Ns_Label_Html, Ns_Label_Html_Centered, Ns_Label_WordWrapped
from neosca.ns_widgets.ns_tables import Ns_StandardItemModel, Ns_TableView


class Ns_Dialog(QDialog):
    class ButtonAlignmentFlag(Enum):
        AlignLeft = 0
        AlignRight = 2

    def __init__(
        self, main, title: str = "", width: int = 0, height: int = 0, resizable=False, **kwargs
    ) -> None:
        """
        ┌———————————┐
        │           │
        │  content  │
        │           │
        │———————————│
        │  buttons  │
        └———————————┘
        """
        super().__init__(main, **kwargs)
        self.main = main
        # https://github.com/BLKSerene/Wordless/blob/main/wordless/wl_dialogs/wl_dialogs.py#L28
        # [Copied code starts here]
        # Dialog size
        if resizable:
            if not width:
                width = self.size().width()

            if not height:
                height = self.size().height()

            self.resize(width, height)
        else:
            if width:
                self.setFixedWidth(width)

            if height:
                self.setFixedHeight(height)
            # Gives the window a thin dialog border on Windows. This style is
            # traditionally used for fixed-size dialogs.
            self.setWindowFlag(Qt.WindowType.MSWindowsFixedSizeDialogHint)
        # [Copied code ends here]
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(str(ICON_PATH)))

        self.layout_content = QGridLayout()
        self.layout_button = QGridLayout()
        self.layout_button.setColumnStretch(1, 1)

        self.grid_layout = QGridLayout()
        self.grid_layout.addLayout(self.layout_content, 0, 0)
        self.grid_layout.addLayout(self.layout_button, 1, 0)
        self.setLayout(self.grid_layout)

    def rowCount(self) -> int:
        return self.layout_content.rowCount()

    def columnCount(self) -> int:
        return self.layout_content.columnCount()

    def addWidget(self, *args, **kwargs) -> None:
        self.layout_content.addWidget(*args, **kwargs)

    def addButtons(self, *buttons, alignment: ButtonAlignmentFlag) -> None:
        layout = QGridLayout()
        for colno, button in enumerate(buttons):
            layout.addWidget(button, 0, colno)
        self.layout_button.addLayout(layout, 0, alignment.value)

    def setColumnStretch(self, column: int, strech: int) -> None:
        self.layout_content.setColumnStretch(column, strech)

    def setRowStretch(self, row: int, strech: int) -> None:
        self.layout_content.setRowStretch(row, strech)

    def bring_to_front(self) -> None:
        self.show()
        self.setWindowState(
            (self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive
        )
        self.raise_()
        self.activateWindow()


class Ns_Dialog_Processing_With_Elapsed_Time(Ns_Dialog):
    started = Signal()
    # Use this to get the place holder, e.g. 0:00:00
    time_format_re = re.compile(r"[^:]")

    def __init__(
        self,
        main,
        title: str = "Please Wait",
        width: int = 500,
        height: int = 0,
        time_format: str = "h:mm:ss",
        interval: int = 1000,
        **kwargs,
    ) -> None:
        super().__init__(main, title=title, width=width, height=height, resizable=False, **kwargs)
        self.time_format = time_format
        self.interval = interval
        self.elapsedtimer = QElapsedTimer()
        self.timer = QTimer()

        # TODO: this label should be exposed
        self.label_status = QLabel("Processing...")
        self.text_time_elapsed_zero = f"Elapsed time: {self.time_format_re.sub('0', time_format)}"
        self.label_time_elapsed = QLabel(self.text_time_elapsed_zero)
        self.label_please_wait = Ns_Label_WordWrapped("The process can take some time, please be patient.")

        self.addWidget(self.label_status, 0, 0)
        self.addWidget(self.label_time_elapsed, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
        self.addWidget(self.label_please_wait, 1, 0, 1, 2)

        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)

        # Bind
        self.timer.timeout.connect(self.update_time_elapsed)
        self.started.connect(self.elapsedtimer.start)
        # If the timer is already running, it will be stopped and restarted.
        self.started.connect(lambda: self.timer.start(self.interval))
        # Either 'accepted' or 'rejected', although 'rejected' is disabled (see rejected below)
        self.finished.connect(self.reset_time_elapsed)
        self.finished.connect(self.timer.stop)

    def reset_time_elapsed(self) -> None:
        self.label_time_elapsed.setText(self.text_time_elapsed_zero)

    def update_time_elapsed(self) -> None:
        time_elapsed: int = self.elapsedtimer.elapsed()
        qtime: QTime = QTime.fromMSecsSinceStartOfDay(time_elapsed)
        self.label_time_elapsed.setText(f"Elapsed time: {qtime.toString(self.time_format)}")

    # Override
    def reject(self) -> None:
        pass

    # Override
    def show(self) -> None:
        self.started.emit()
        return super().show()

    # Override
    def open(self) -> None:
        self.started.emit()
        return super().open()

    # Override
    def exec(self) -> int:
        self.started.emit()
        return super().exec()


class Ns_Dialog_TextEdit(Ns_Dialog):
    def __init__(self, main, title: str = "", text: str = "", **kwargs) -> None:
        super().__init__(main, title=title, resizable=True, **kwargs)
        self.textedit = QTextEdit(text)
        self.textedit.setReadOnly(True)
        # https://stackoverflow.com/questions/74852753/indent-while-line-wrap-on-qtextedit-with-pyside6-pyqt6
        indentation: int = self.fontMetrics().horizontalAdvance("abcd")
        self.fmt_textedit = QTextBlockFormat()
        self.fmt_textedit.setLeftMargin(indentation)
        self.fmt_textedit.setTextIndent(-indentation)

        self.button_copy = QPushButton("Copy")
        self.button_copy.clicked.connect(self.copy)

        self.button_close = QPushButton("Close")
        self.button_close.clicked.connect(self.reject)

        self.addButtons(self.button_copy, alignment=Ns_Dialog.ButtonAlignmentFlag.AlignLeft)
        self.addButtons(self.button_close, alignment=Ns_Dialog.ButtonAlignmentFlag.AlignRight)

    def setText(self, text: str) -> None:
        self.textedit.setText(text)
        cursor = QTextCursor(self.textedit.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeBlockFormat(self.fmt_textedit)

    def copy(self) -> None:
        self.textedit.selectAll()
        self.textedit.copy()

    # Override
    def show(self) -> None:
        # Add self.textedit lastly to allow adding custom widgets above
        self.addWidget(self.textedit, self.rowCount(), 0, 1, self.columnCount())
        return super().show()

    # Override
    def open(self) -> None:
        # Add self.textedit lastly to allow users add custom widgets above
        self.addWidget(self.textedit, self.rowCount(), 0, 1, self.columnCount())
        return super().open()

    # Override
    def exec(self) -> int:
        # Add self.textedit lastly to allow users add custom widgets above
        self.addWidget(self.textedit, self.rowCount(), 0, 1, self.columnCount())
        return super().exec()


class Ns_Dialog_TextEdit_SCA_Matched_Subtrees(Ns_Dialog_TextEdit):
    def __init__(self, main, index: Union[QModelIndex, QPersistentModelIndex], **kwargs):
        super().__init__(main, title="Matches", width=500, height=300, **kwargs)
        self.file_name = index.model().verticalHeaderItem(index.row()).text()
        self.sname = index.model().horizontalHeaderItem(index.column()).text()
        self.matched_subtrees: List[str] = index.data(Qt.ItemDataRole.UserRole)
        self.setText("\n".join(self.matched_subtrees))

        self.label_summary = Ns_Label_WordWrapped(
            f'{len(self.matched_subtrees)} occurrences of "{self.sname}" in "{self.file_name}"'
        )
        self.addWidget(self.label_summary)


class Ns_Dialog_TextEdit_Citing(Ns_Dialog_TextEdit):
    def __init__(self, main, **kwargs):
        super().__init__(main, title="Citing", **kwargs)
        with open(CITING_PATH, encoding="utf-8") as f:
            self.style_citation_mapping = json.load(f)

        self.label_citing = Ns_Label_WordWrapped(
            f"If you use {__title__} in your research, please cite as follows."
        )
        self.setText(next(iter(self.style_citation_mapping.values())))
        self.label_choose_citation_style = QLabel("Choose citation style: ")
        self.combobox_choose_citation_style = QComboBox()
        self.combobox_choose_citation_style.addItems(tuple(self.style_citation_mapping.keys()))
        self.combobox_choose_citation_style.currentTextChanged.connect(
            lambda key: self.setText(self.style_citation_mapping[key])
        )

        self.addWidget(self.label_citing, 0, 0, 1, 2)
        self.addWidget(self.label_choose_citation_style, 1, 0)
        self.addWidget(self.combobox_choose_citation_style, 1, 1)
        self.setColumnStretch(1, 1)


class Ns_Dialog_TextEdit_Err(Ns_Dialog_TextEdit):
    def __init__(self, main, ex: Exception, **kwargs) -> None:
        super().__init__(main, title="Error", width=500, height=300, **kwargs)
        # https://stackoverflow.com/a/35712784/20732031
        trace_back = "".join(traceback.TracebackException.from_exception(ex).format())
        meta_data = "\n".join(
            ("", "Metadata:", f"  {__title__} version: {__version__}", f"  Platform: {sys.platform}")
        )
        self.setText(trace_back + meta_data)

        self.label_desc = Ns_Label_WordWrapped(
            f"An error occurred. Please send the following error messages to <a href='{__email__}'>{__email__}</a> to contact the author for support."
        )
        self.addWidget(self.label_desc)


class Ns_Dialog_Table(Ns_Dialog):
    def __init__(
        self,
        main,
        title: str,
        text: str,
        tableview: Ns_TableView,
        export_filename: Optional[str] = None,
        width: int = 500,
        height: int = 300,
        resizable=True,
    ) -> None:
        super().__init__(main, title=title, width=width, height=height, resizable=resizable)
        self.tableview: Ns_TableView = tableview
        self.layout_content.addWidget(Ns_Label_WordWrapped(text), 0, 0)
        self.layout_content.addWidget(tableview, 1, 0)

        self.button_ok = QPushButton("OK")
        self.button_ok.clicked.connect(self.accept)
        self.addButtons(self.button_ok, alignment=Ns_Dialog.ButtonAlignmentFlag.AlignRight)

        if export_filename is not None:
            self.button_export_table = QPushButton("Export table...")
            self.button_export_table.clicked.connect(lambda: self.tableview.export_table(export_filename))
            self.addButtons(self.button_export_table, alignment=Ns_Dialog.ButtonAlignmentFlag.AlignLeft)


class Ns_Dialog_Table_Acknowledgments(Ns_Dialog_Table):
    def __init__(self, main, **kwargs) -> None:
        with open(ACKS_PATH, encoding="utf-8") as f:
            acks = json.load(f)
        model_ack = Ns_StandardItemModel(main)
        model_ack.setHorizontalHeaderLabels(("Name", "Version", "Authors", "License"))
        model_ack.setRowCount(len(acks))
        tableview_ack = Ns_TableView(main, model=model_ack, has_vertical_header=False)
        for rowno, ack in enumerate(acks):
            cols = (
                Ns_Label_Html(f"<a href='{ack['homepage']}'>{ack['name']}</a>"),
                Ns_Label_Html_Centered(ack["version"]),
                Ns_Label_Html(ack["authors"]),
                Ns_Label_Html_Centered(
                    f"<a href='{ack['license_file']}'>{ack['license']}</a>"
                    if ack["license_file"]
                    else f"{ack['license']}"
                ),
            )
            for colno, label in enumerate(cols):
                tableview_ack.setIndexWidget(model_ack.index(rowno, colno), label)
        thanks = """NeoSCA is greatly indebted to the open source projects below without which it could never have been possible. As the project is a fork of L2SCA and LCA, I want to express my sincere gratitude to the original author Xiaofei Lu (陆小飞) for his expertise and efforts, and I am grateful for the opportunity to build upon his work."""
        super().__init__(main, title="Acknowledgments", text=thanks, tableview=tableview_ack)
