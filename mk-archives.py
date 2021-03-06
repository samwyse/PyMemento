from __future__ import absolute_import, division, print_function, unicode_literals

import re, sys
from textwrap import fill

PY3 = sys.version_info >= (3,)
if PY3:
    from urllib.request import urlopen
    from html.parser import HTMLParser
else:
    from urllib2 import urlopen
    from HTMLParser import HTMLParser


last_component_re = re.compile(r'\/(\w+)\/?$')
example_url_re = re.compile(r'(https?\:\/\/.*\/)(https?\:\/\/.*)')
yyyymmdd_re = re.compile(r'\/[12][90]\d\d\d\d\d\d')


class ArchivePageParser(HTMLParser):
    def __init__(self):
        self.state = 0
        self.examples = []
        self.flavor = []
        if PY3:
            super().__init__()
        else:
            HTMLParser.__init__(self)
    def handle_starttag(self, tag, attrs):
        if tag == 'h3':
            id = dict(attrs).get('id', '')
            if id == 'ArchiveContent':
                self.state = 9
                self.flavor = []
            else:
                self.state = 0
        if tag == 'ul' and self.state == 0:
            self.state = 1
        if tag == 'li' and self.state == 1:
            self.state = 2
        if tag == 'code' and self.state == 2:
            self.state = 3
    def handle_endtag(self, tag):
        if tag == 'ul' and self.state == 1:
            self.state = 0
        if tag == 'li' and self.state == 2:
            self.state = 1
        if tag == 'code' and self.state == 3:
            self.state = 2
    def handle_data(self, data):
        if self.state == 3:
            match = example_url_re.match(data)
            if match:
                self.examples.append(match.group(1, 2))
        if self.state == 9:
            self.flavor.append(data)


class IndexPageParser(HTMLParser):
    def __init__(self, code_generator):
        self.code_generator = code_generator
        self.state = 0
        if PY3:
            super().__init__()
        else:
            HTMLParser.__init__(self)
    def handle_starttag(self, tag, attrs):
        if tag == 'ul' and self.state == 0:
            self.state = 1
        if tag == 'li' and self.state == 1:
            self.state = 2
        if tag == 'a' and self.state == 2:
            href = dict(attrs)['href']
            match = last_component_re.search(href)
            if match:
                self.code_generator.class_def(match)
    def handle_endtag(self, tag):
        if tag == 'ul' and self.state == 1:
            self.state = 0
        if tag == 'li' and self.state == 2:
            self.state = 1


class CodeGen(object):
    '''Put all code generation in one place.'''

    def __init__(self, fname):
        self.file = open(fname + '.py', mode='w')
        self.exports = []

    def print(self, *args, **kwds):
        kwds['file'] = self.file
        print(*args, **kwds)

    def prolog(self):
        self.print('''\
## Auto-generated code.

"""
doc string
"""

from memento import Memento, register_as
''')

    def epilog(self):
        self.print('''
if __name__ == "__main__":
    import doctest
    doctest.testmod()
''')
        self.file.flush()

    class_def_template = '''
@register_as(%(group)r)
class %(title)s(Memento):
    """
%(flavor)s

>>> obj = %(title)s().get_timegate(for_uri='%(for_uri)s')
>>> obj.first
"""'''
              
    def class_def(self, match):
        http_response = urlopen(match.string)
        archive_parser = ArchivePageParser()
        if PY3:
            buffer = str(http_response.read(), 'utf-8')
        else:
            buffer = http_response.read()
        archive_parser.feed(buffer)
        if archive_parser.examples:
            flavor = ''.join(s for s in archive_parser.flavor[1:]).strip()
            flavor = re.compile(r'\s+').sub(' ', flavor)
            group = match.group(1)
            title = group.title()
            self.exports.append(title)
            for_uri = 'http://example.org/example'
            for example in archive_parser.examples:
                if len(example) > 1:
                    for_uri = example[1]
            self.print(self.class_def_template % {
                'flavor': fill(flavor),
                'group': group,
                'title': title,
                'for_uri': for_uri,
                })
            for example in archive_parser.examples:
                if yyyymmdd_re.search(example[0]):
                    continue
                var = 'timemap' if 'timemap' in example[0] else 'timegate'
                self.print('    %s_template = %r' % (var, example[0] + '%s'))


code_gen = CodeGen('archives')
code_gen.prolog()

depot = urlopen('http://mementoweb.org/depot/')
index_parser = IndexPageParser(code_gen)
if PY3:
    buffer = str(depot.read(), 'utf-8')
else:
    buffer = depot.read()
index_parser.feed(buffer)

code_gen.epilog()
