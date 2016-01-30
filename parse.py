"""
Possible bug:

```
first:
    if (1) goto second;
```

pycparser doesn't seem to visit the statement that a label captures?
"""

import pycparser
from pycparser.c_ast import *
from collections import namedtuple

NodeExtra = namedtuple("ExtraNode", "parents offset level node")

def get_main(ast):
    for node in ast.ext:
        if type(node) == FuncDef and node.decl.name == "main":
            return node

    return None

def pair_goto_labels(labels, conditional_gotos):
    """Return a dictionary of (label, [goto_partners]) pairs.
    The dictionary's keys are NodeExtras containing labels, and the values are
    lists of NodeExtras containing goto statements whose targets are the label.
    """
    label_dict = {}

    for extra_label in labels:
        label = extra_label.node
        label_dict[label.name] = []

        for conditional_extra in conditional_gotos:
            cond = conditional_extra.node
            goto = cond.iftrue
            target = goto.name
            if target == label.name:
                label_dict[label.name].append(conditional_extra)

    return label_dict

def remove_siblings(extra_label, extra_conditional):
    """TODO: Docstring for remove_siblings.

    :extra_label: TODO
    :extra_conditional: TODO
    :returns: TODO

    """
    assert(are_siblings(extra_label, extra_conditional))

    compound = extra_label.parents[-1]
    conditional = extra_conditional.node
    label = extra_label.node

    label_index, cond_index = None, None

    for index, node in enumerate(compound.block_items):
        if node == conditional:
            cond_index = index
        elif node == label:
            label_index = index

    assert(label_index >= 0 and cond_index >= 0)

    if label_index >= cond_index:
        # Goto is before the label.
        # In this case, we guard the statements from the goto to the label in a
        # new conditional.
        cond = UnaryOp("!", conditional.cond)
        in_between = compound.block_items[cond_index+1:label_index]
        between_compound = Compound(in_between)
        guard = If(cond, between_compound, None)

        pre_goto = compound.block_items[:cond_index]
        post_conditional = compound.block_items[label_index:]
        compound.block_items = pre_goto + [guard] + post_conditional
    else:
        raise NotImplementedError("Ooops!")

def are_siblings(extra_one, extra_two):
    """Check if two NodeExtras are siblings.
    They are siblings iff they both exist unnested in a sequence of
    statements. Currently, this is checked by looking to see if
        1. Both are under a Compound node, and
        2. Both have the _same_ Compound node as a parent.
    I justify this by saying that there can't be any sequence of statements if
    they aren't inside of a Compound.
    """
    one_parent = extra_one.parents[-1]
    two_parent = extra_two.parents[-1]

    under_compound = (type(one_parent) == Compound and
                        type(two_parent) == Compound)

    return under_compound and one_parent == two_parent

class GotoLabelFinder(NodeVisitor):
    """Visitor that will find every goto or label under a given node.

    The results will be two lists of NodeExtra's, self.gotos and self.labels,
    complete with the offset, level, and parent stack for each.
    The self.gotos list is actually a list of If NodeExtras, with the offset,
    level, and parent stack of the goto. This isn't so strange, as we're treating
    the conditional and goto as one unit.
    """

    def __init__(self):
        self.offset = 0
        self.level = 0
        self.gotos = []
        self.labels = []
        self.parents = []

    def level_visit(self, node):
        self.level += 1
        self.generic_visit(node)
        self.level -= 1

    def generic_visit(self, node):
        self.parents.append(node)
        for access, child in node.children():
            self.visit(child)

        self.parents.pop()

    def visit_Goto(self, node):
        parents = list(self.parents)
        parent = parents[-1]

        if type(parent) != If:
            line = node.coord.line
            raise NotImplementedError("unsupported unconditional goto statement at line {}".format(line))

        self.gotos.append(NodeExtra(parents[:-1], self.offset, self.level, parent))
        self.offset += 1

    def visit_Label(self, node):
        parents = list(self.parents)
        self.labels.append(NodeExtra(parents, self.offset, self.level, node))
        self.offset += 1

    def visit_If(self, node):
        self.level_visit(node)
    def visit_While(self, node):
        self.level_visit(node)
    def visit_DoWhile(self, node):
        self.level_visit(node)
    def visit_Switch(self, node):
        self.level_visit(node)
    def visit_For(self, node):
        self.level_visit(node)

    def visit_Compound(self, node):
        # Only increment the level if we're not a part of a "leveler."
        if not type(self.parents[-1]) in [If, While, DoWhile, Switch, For]:
            self.level += 1
            self.generic_visit(node)
            self.level -= 1
        else:
            self.generic_visit(node)

def do_it(t, d):
    for extra_label in t.labels:
        label = extra_label.node
        for extra_conditional in d[label.name]:
            if are_siblings(extra_label, extra_conditional):
                print("Siblings!")
                remove_siblings(extra_label, extra_conditional)
            else:
                print("Not!")

if __name__ == "__main__":
    ast = pycparser.parse_file("./test.c", use_cpp=True,
                    cpp_args="-I/usr/share/python3-pycparser/fake_libc_include")
    main = get_main(ast)
    t = GotoLabelFinder()
    t.visit(main)
    d = pair_goto_labels(t.labels, t.gotos)
    main.body.show()
    do_it(t, d)
    main.body.show()