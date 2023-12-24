#!/usr/bin/env python3

import os
from neosca.ns_nlp import Ns_NLP_Stanza

from .base_tmpl import BaseTmpl
from .cmdline_tmpl import text as cmdline_text


class TestNLPStanza(BaseTmpl):
    def setUp(self):
        self.processors = Ns_NLP_Stanza.processors
        return super().setUp()

    def test_private_nlp(self):
        processors = ("tokenize",)
        doc = Ns_NLP_Stanza._nlp(cmdline_text, processors=processors)
        self.assertSetEqual(doc.processors, set(processors))

        doc2 = Ns_NLP_Stanza._nlp(doc2)
        self.assertEqual(doc2.processors, self.processors)

    def test_nlp(self):
        default_cache_path = "cmdline_text.pickle.lzma"
        self.assertFileNotExist(default_cache_path)
        processors = ("tokenize", )
        doc = Ns_NLP_Stanza.nlp(cmdline_text, processors=processors, is_cache_for_future_runs=True)
        self.assertSetEqual(doc.processors, set(processors))
        self.assertFileExists(default_cache_path)
        os.remove(default_cache_path)

        doc2 = Ns_NLP_Stanza.nlp(doc, processors=self.processors, is_cache_for_future_runs=False)
        self.assertSetEqual(doc2.processors, set(self.processors))
        self.assertFileNotExist(default_cache_path)

    def test_doc_serialized_conversion(self):
        doc = Ns_NLP_Stanza._nlp(cmdline_text)
        serialized = Ns_NLP_Stanza.doc2serialized(doc)
        doc2 = Ns_NLP_Stanza.serialized2doc(serialized)
        self.assertEqual(doc.processors, doc2.processors)

