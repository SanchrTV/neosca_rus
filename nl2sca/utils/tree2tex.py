import re


class Tree2Tex:
    preamble = (
        "\\documentclass[a4paper]{article}\n"
        "\\usepackage{qtree}\n"
        "\\usepackage{adjustbox}\n"
        "\\usepackage[hmargin=0.8in,vmargin=1in]{geometry}\n"
        "\\usepackage{hyperref}\n"
        "\\renewcommand\\thesection{}\n"
        "\\begin{document}"
    )
    adjustbox_begin = (
        "\\begin{adjustbox}{width={\\textwidth},"
        "totalheight={\\textheight},keepaspectratio}"
    )
    adjustbox_end = "\\end{adjustbox}"
    last = "\\end{document}"

    def __init__(self, trees):
        """
        :param trees: trees generated by Stanford Parser, as a string
            (ROOT
              (S
                (NP (DT This))
                (VP (VBZ is)
                  (NP (DT an) (NN example)))
                (. .)))
        """
        self.trees = trees

    def _convert_trees(self):
        """
        Convert each tree to a LaTeX command according to the grammar of Qtree,
        a LaTeX tree-drawing package, see
        https://www.ctan.org/pkg/qtree?lang=en

        :return: list of converted trees
        """
        trees_tex = re.findall(r"\r?\n\s*(?:\([^\r\n]*|\r?\n)", self.trees)
        # find (1) lines with '(' as the first non-blank character, and
        #      (2) blank lines
        trees_tex = "".join(trees_tex).strip()
        trees_tex = re.sub(r"(\r?\n) +", r"\1", trees_tex)
        # remove whitespaces at the beginning of each line
        trees_tex = re.sub(r"(?<=[^\r\n])\r?\n", r" ", trees_tex)
        # flatten trees, e.g.
        # (ROOT
        #   (S
        #     (NP (DT This))
        #     (VP (VBZ is)
        #       (NP (DT an) (NN example)))
        #          )) will become:
        # (ROOT (S (NP (DT This)) (VP (VBZ is) (NP (DT an) (NN example)))))

        trees_tex = re.sub(r"\(\W[^)]*\)", r"", trees_tex)
        # remove punctuation marks
        trees_tex = trees_tex.replace("(", "[.").replace(")", " ]")
        # replace parentheses with square brackets
        # Closing brackets should be preceded by a whitespace, otherwise LaTeX
        # will report an error. This might be a bug of Qtree, if not an
        # intended design.

        trees_tex = trees_tex.replace('\\', '\\textbackslash')
        # escape special symbols, see
        # https://www.tug.org/tutorials/tugindia/chap02-scr.pdf, 2.3 Characters
        trees_tex = trees_tex.replace("#", "\\#")
        trees_tex = trees_tex.replace("$", "\\$")  # ibid
        trees_tex = trees_tex.replace("%", "\\%")  # ibid
        trees_tex = trees_tex.replace("\\^", "\\^{}")  # ibid
        trees_tex = trees_tex.replace("_", "\\_")  # ibid
        trees_tex = trees_tex.replace("&", "\\&")  # ibid
        trees_tex = trees_tex.replace("{", "\\{")  # ibid
        trees_tex = trees_tex.replace("}", "\\}")  # ibid
        trees_tex = trees_tex.replace("~", "\\textasciitilde")  # ibid

        trees_tex = re.sub(r"(\r?\n)([^\r\n])", r"\1\\Tree \2", trees_tex)
        trees_tex = "\\Tree " + trees_tex
        # add '\Tree' at the beginning of each tree

        trees_tex = re.sub(r" {2,}", " ", trees_tex)
        return re.split(r"(?:\r?\n){2,}", trees_tex)

    def to_latex(self):
        """
        Convert trees to LaTeX format
        """
        trees_tex = self._convert_trees()
        final_tex = self.preamble + "\n"
        for i, tree_tex in enumerate(trees_tex):
            final_tex += (
                f"\\section{{Tree/Subtree {i+1}}}\n"
                f"{self.adjustbox_begin}\n"
                f"{tree_tex}\n"
                f"{self.adjustbox_end}\n"
                "\\newline\n"
            )
        final_tex += self.last
        return final_tex
