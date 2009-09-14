"""

CTemplate
=========

This is CTemplate, a quick hack to demo compiling Django templates to C via
Cython. You can use a CTemplate object just as you would a regular Template
object:

  >>> CTemplate("Hello {{ name }}").render(Context({'name': 'rebon'}))
  'Hello rebon'

Behind the scenes, the Template object is compiled via Cython to a shared
object (hopefully) providing a faster 'render' method for that template. If
CTemplate encounters a node that it cannot compile directly to C, it is pickled
and executed "dynamically" at run-time. To demo this, comment out `visit_IfNode'
below and rerun __main__.

Speedups of at least 5X-10X should be expected, assuming you do not have any
uncompiled template nodes. In contrast, Jinja2 claims a 2X speed increase,
although I am grossly misrepresentating their project here.

Performance comparisons are rather biased towards Django - in a typical Django
project the Template object is constructed on *each* render, degrading the
performance by at least one order of magnitude.

I release this code under the same license as Django itself.

  -- Chris Lamb <lamby@debian.org>  Mon, 14 Sep 2009 23:57:39 +0100

"""

import pickle
import tempfile
import pyximport

from django.template import Context, Template

__all__ = ('CTemplate', 'Context')

render_t = Template("""
# Automatically generated by CTemplate, do not edit.

{% if pickle_nodes %}
from pickle import loads
n = loads({{ nodes }})
{% endif %}

cdef inline char* get(dict context, char *key):
    # Only call PyBytes_FromString once
    cdef bytes x = <bytes>key
    cdef object obj

    if x in context:
        obj = context[x]
        if isinstance(obj, unicode):
            return obj
        alias = unicode(obj)
        return alias

    return ''

def render(context):
    cdef dict c = {}
    update_fn = c.update
    for d in reversed(context.dicts):
        update_fn(<dict>d)

    return {{ value }}
""")

class CTemplate(object):
    def __init__(self, template_string):
        self.module = None

        src = tempfile.NamedTemporaryFile(suffix='.pyx')

        try:
            src.write(Compiler().visit(Template(template_string)))
            src.flush()
            self.module = pyximport.load_module('template', src.name)
        finally:
            src.close()

    def render(self, context):
        return self.module.render(context)

class Compiler(object):
    def __init__(self):
        self.reentrant_nodes = []

    def visit(self, node):
        attrname = "visit_%s" % node.__class__.__name__

        if hasattr(self, attrname):
            return getattr(self, attrname)(node)

        self.reentrant_nodes.append(node)

        return 'n[%d].render(context)' % (len(self.reentrant_nodes) - 1)

    def visit_Template(self, node):
        val = self.visit(node.nodelist)

        return render_t.render(Context({
           'value': val,
           'nodes': repr(pickle.dumps(self.reentrant_nodes)),
           'pickle_nodes': bool(self.reentrant_nodes),
        }, autoescape=False))

    def visit_NodeList(self, node):
        if len(node) == 0:
            return repr('')
        if len(node) == 1:
            return self.visit(node[0])

        return r'u"".join([%s])' % (', '.join(self.visit(x) for x in node))
    visit_DebugNodeList = visit_NodeList

    def visit_TextNode(self, node):
        return repr(node.s)

    def visit_VariableNode(self, node):
        return self.visit(node.filter_expression)
    visit_DebugVariableNode = visit_VariableNode

    def visit_FilterExpression(self, node):
        assert len(node.filters) == 0, "Filters not implemented yet"

        if node.var.literal is None:
            return "get(c, '%s')" % node.token
        else:
            return node.var.var

    def visit_IfNode(self, node):
        assert len(node.bool_exprs) == 1, "Logic not implemented yet"
        assert not node.bool_exprs[0][0], "'not' not implemented yet"

        return "((%s) if (%s) else (%s))" % (
            self.visit(node.nodelist_true),
            self.visit(node.bool_exprs[0][1]),
            self.visit(node.nodelist_false),
        )

    def visit_CommentNode(self, node):
        return repr(u'')

if __name__ == '__main__':
    import time

    template_string = """Hello {{ name }} {% comment %}foo{% endcomment %}"""
    context = Context({'name': u"rebon"})

    ctemplate = CTemplate(template_string)
    dtemplate = Template(template_string)

    start = time.time()
    for x in xrange(2000):
        dtemplate.render(context)
        #Template(template_string).render(context) # Real-world emulation
    django_time = time.time() - start

    start = time.time()
    for x in xrange(2000):
        ctemplate.render(context)
    ctemplate_time = time.time() - start

    print "CTemplate is ~%.1fX faster" % (django_time / ctemplate_time)