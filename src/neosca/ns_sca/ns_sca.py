#!/usr/bin/env python3

import logging
import os
import os.path as os_path
import sys
from typing import Dict, List, Optional, Set, Tuple

from neosca.ns_about import __title__
from neosca.ns_io import Ns_Cache, Ns_IO
from neosca.ns_sca.querier import Ns_Tregex
from neosca.ns_sca.structure_counter import StructureCounter


class Ns_SCA:
    def __init__(
        self,
        ofile_freq: str = "result.csv",
        oformat_freq: str = "csv",
        odir_matched: str = "",
        selected_measures: Optional[List[str]] = None,
        precision: int = 4,
        is_reserve_parsed: bool = True,
        is_use_past_parsed: bool = True,
        is_reserve_matched: bool = False,
        is_stdout: bool = False,
        is_skip_querying: bool = False,
        is_skip_parsing: bool = False,
        is_auto_save: bool = True,
        config: Optional[str] = None,
    ) -> None:
        self.ofile_freq = ofile_freq
        self.oformat_freq = oformat_freq
        self.odir_matched = odir_matched
        self.selected_measures = selected_measures
        self.precision = precision
        self.is_reserve_parsed = is_reserve_parsed
        self.use_cache = is_use_past_parsed
        self.is_reserve_matched = is_reserve_matched
        self.is_stdout = is_stdout
        self.is_skip_querying = is_skip_querying
        self.is_skip_parsing = is_skip_parsing
        self.is_auto_save = is_auto_save

        self.user_data, self.user_structure_defs, self.user_snames = self.load_user_config(config)
        logging.debug(f"[{__title__}] user_snames: {self.user_snames}")

        if selected_measures is not None:
            StructureCounter.check_undefined_measure(selected_measures, self.user_snames)

        self.counters: List[StructureCounter] = []
        self.is_stanford_tregex_initialized = False

    def update_options(self, kwargs: Dict):
        self.__init__(**kwargs)

    def load_user_config(self, config: Optional[str]) -> Tuple[dict, List[dict], Optional[Set[str]]]:
        user_data: dict = {}
        user_structure_defs: List[Dict[str, str]] = []
        user_snames: Optional[Set[str]] = None

        if config is not None:
            user_data = Ns_IO.load_json(config)
            user_structure_defs = user_data["structures"]
            user_snames = StructureCounter.check_user_structure_def(user_structure_defs)

        return user_data, user_structure_defs, user_snames

    def ensure_stanford_tregex_initialized(self) -> None:
        if not self.is_stanford_tregex_initialized:
            self.tregex = Ns_Tregex()
            self.is_stanford_tregex_initialized = True

    def query_against_trees(self, trees: str, counter: StructureCounter) -> StructureCounter:
        self.ensure_stanford_tregex_initialized()
        counter = self.tregex.query(
            counter,
            trees,
            is_reserve_matched=self.is_reserve_matched,
            odir_matched=self.odir_matched,
            is_stdout=self.is_stdout,
        )
        return counter

    def parse_text(self, text: str, cache_path: Optional[str] = None) -> str:
        if self.is_skip_parsing:  # assume input as parse trees
            return text

        from neosca.ns_nlp import Ns_NLP_Stanza

        trees = Ns_NLP_Stanza.get_constituency_tree(text, cache_path=cache_path)
        return trees

    def parse_ifile(self, ifile: str) -> Optional[str]:
        from stanza import Document

        from neosca.ns_nlp import Ns_NLP_Stanza

        if self.is_skip_parsing:
            # Assume input as parse trees
            return Ns_IO.read_txt(ifile, is_guess_encoding=False)

        if self.use_cache:
            cache_path, cache_available = Ns_Cache.get_cache_path(ifile)
            if cache_available:
                logging.info(f"Loading cache: {cache_path}.")
                doc: Document = Ns_NLP_Stanza.serialized2doc(Ns_IO.load_lzma(cache_path))
                return Ns_NLP_Stanza.get_constituency_tree(doc, cache_path=cache_path)
        else:
            cache_path = None
            cache_available = False

        if (text := Ns_IO.read_file(ifile)) is None:
            return None
        try:
            trees = self.parse_text(text, cache_path)
        except BaseException as e:
            # If cache is generated at current run, remove it as it is potentially broken
            if cache_path is not None and os_path.exists(cache_path) and not cache_available:
                os.remove(cache_path)
            raise e
        else:
            return trees

    def run_on_text(self, text: str, ifile: str = "cmdline_text") -> None:
        trees: str = self.parse_text(text)

        if self.is_skip_querying:
            return

        counter = StructureCounter(
            ifile,
            selected_measures=self.selected_measures,
            user_structure_defs=self.user_structure_defs,
        )
        counter = self.query_against_trees(trees, counter)
        self.counters.append(counter)
        if self.is_auto_save:
            self.write_value_output()

    def parse_and_query_ifile(self, ifile: str) -> Optional[StructureCounter]:
        trees = self.parse_ifile(ifile)
        if trees is None:
            return None

        counter = StructureCounter(
            ifile,
            selected_measures=self.selected_measures,
            user_structure_defs=self.user_structure_defs,
            precision=self.precision,
        )
        return self.query_against_trees(trees, counter)

    def parse_ifiles(self, ifiles: List[str]):
        total = len(ifiles)
        for i, ifile in enumerate(ifiles, 1):
            logging.info(f'[{__title__}] Processing "{ifile}" ({i}/{total})...')
            self.parse_ifile(ifile)

    def parse_subfiles_list(self, subfiles_list: List[List[str]]):
        for subfiles in subfiles_list:
            self.parse_ifiles(subfiles)

    def parse_and_query_ifiles(self, ifiles):
        total = len(ifiles)
        for i, ifile in enumerate(ifiles, 1):
            logging.info(f'[{__title__}] Processing "{ifile}" ({i}/{total})...')
            counter = self.parse_and_query_ifile(ifile)
            if counter is None:
                continue
            self.counters.append(counter)

    def parse_and_query_subfiles_list(self, subfiles_list: List[List[str]]):
        for subfiles in subfiles_list:
            total = len(subfiles)
            parent_counter = StructureCounter(
                selected_measures=self.selected_measures,
                user_structure_defs=self.user_structure_defs,
                precision=self.precision,
            )

            for i, subfile in enumerate(subfiles, 1):
                logging.info(f'[{__title__}] Processing "{subfile}" ({i}/{total})...')
                child_counter = self.parse_and_query_ifile(subfile)
                if child_counter is None:
                    continue
                parent_counter += child_counter

            self.tregex.set_all_values(parent_counter, "")
            self.counters.append(parent_counter)

    def run_on_ifiles(
        self, files: Optional[List[str]] = None, subfiles_list: Optional[List[List[str]]] = None
    ) -> None:
        if files is None:
            files = []
        if subfiles_list is None:
            subfiles_list = []

        if self.is_skip_querying:
            self.parse_ifiles(files)
            self.parse_subfiles_list(subfiles_list)
            return

        self.parse_and_query_ifiles(files)
        self.parse_and_query_subfiles_list(subfiles_list)
        if self.is_auto_save:
            self.write_value_output()

    def write_value_output(self) -> None:
        logging.debug(f"[{__title__}] Writting counts and/or frequencies...")

        counters = self.counters
        if len(counters) == 0:
            raise ValueError("empty counter list")

        oformat_freq = self.oformat_freq
        if oformat_freq not in ("csv", "json"):
            raise ValueError(f'oformat_freq {oformat_freq} not in ("csv", "json")')

        sname_value_maps: List[Dict[str, str]] = [counter.get_all_values() for counter in counters]

        handle = sys.stdout if self.is_stdout else open(self.ofile_freq, "w", encoding="utf-8", newline="")  # noqa: SIM115

        if oformat_freq == "csv":
            import csv

            fieldnames = sname_value_maps[0].keys()
            writer = csv.DictWriter(handle, fieldnames=fieldnames)

            writer.writeheader()
            writer.writerows(sname_value_maps)

        else:
            import json

            json.dump(sname_value_maps, handle)

        handle.close()
