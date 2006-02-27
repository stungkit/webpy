"""template.py: simple, elegant templating"""
__author__ = "Aaron Swartz <me@aaronsw.com>"
__version__ = 0.003

from web import storage, group, htmlquote
import re
# differences from python:
#  - you can use the expression inside if, while blocks
#  - special for loop attributes, like django?
#  - you can check to see if a variable is defined (perhaps w/ get func?)
#  - for: has an optional else: 
# all these are probably good ideas for python...

# todo:
#  protect against accessing __vars__ (e.g. None)
#  continue, break, etc.
#  nested blocks (for within if, etc.)
#  better getable, expr support
#    inline arrays, tuples, dictionaries
#  code blocks
#  tracebacks

MAX_ITERS = 100000

# http://docs.python.org/ref/identifiers.html
r_var = '[a-zA-Z_][a-zA-Z0-9_]*'

class ParseError(Exception): pass
class Parser:
    def __init__(_, text):
        _.t = text
        _.p = 0
        _._lock = [False]
    
    def lock(_):
        _._lock[-1] = True
    
    def curline(_):
        return _.t[:_.p].count('\n')+1
        
    def csome(_):
        return repr(_.t[_.p:_.p+5]+'...')

    def Error(_, x, y=None):
        if y is None: y = _.csome()
        raise ParseError, "expected %s, got %s (line %s)" % (x, y, _.curline())
    
    def q(_, f):
        def internal(*a, **kw):
            checkp = _.p
            _._lock.append(False)
            try:
                q = f(*a, **kw)
            except ParseError:
                if _._lock[-1]:
                    raise
                _.p = checkp
                _._lock.pop()
                return False
            _._lock.pop()
            return q or True
        return internal
    
    def tokr(_, t): 
        text = _.c(len(t))
        if text != t:
            _.Error(repr(t), repr(text))
        return t
    
    def ltokr(_, *l):
        for x in l:
            o = _.tokq(x)
            if o: return o
        _.Error('one of '+repr(l))
    
    def rer(_, r):
        x = re.match(r, _.t[_.p:]) #@@re_compile
        if not x:
            _.Error('r'+repr(r))
        return _.tokr(x.group())
    
    def endr(_):
        if _.p != len(_.t):
            _.Error('EOF')
        
    def c(_, n=1):
        out = _.t[_.p:_.p+n]
        if out == '' and n != 0:
            _.Error('character', 'EOF')
        _.p += n
        return out

    def lookbehind(_, t):
        return _.t[_.p-len(t):_.p] == t
    
    def __getattr__(self, a):
        if a.endswith('q'):
            return self.q(getattr(self, a[:-1]+'r'))
        raise AttributeError, a

class TemplateParser(Parser):
    def __init__(self, *a, **kw):
        Parser.__init__(self, *a, **kw)
        self.curws = ''
        self.curind = ''
        
    def o(_, *a):
        return a+('lineno', _.curline())
    
    def go(_): 
        # maybe try to do some traceback parsing/hacking
        return _.gor()
    
    def gor(_):
        header = _.defwithq()
        results = _.lines(start=True)
        _.endr()
        return header, results
    
    def ws(_):
        n = 0
        while _.tokq(" "): n += 1
        return " " * n
    
    def defwithr(_):
        _.tokr('$def with ')
        _.lock()
        _.tokr('(')
        args = []
        kw = []
        x = _.varq() # NOTE: just rer
        while x:
            if _.tokq('='):
                v = _.exprr()
                kw.append((x[1], v))
            else: 
                args.append(x[1])
            x = _.tokq(', ') and _.varq() # NOTE: ditto
        _.tokr(')\n')
        return _.o('defwith', args, kw)

    def setr(_):
        _.tokr('$set ')
        _.lock()
        what = _.varr() # NOTE: just rer
        _.tokr(':')
        body = _.lines()
        return _.o('set', what, 'body', body)

    def ifr(_):
        _.tokr("$if ")
        _.lock()
        expr = _.exprr()
        _.tokr(":")
        ifc = _.lines()
        
        elifs = []
        while _.tokq(_.curws+_.curind+'$elif '):
            v = _.exprr()
            _.tokr(':')
            c = _.lines()
            elifs.append(('expr', v, 'code', c))
        
        if _.tokq(_.curws+_.curind+"$else:"): elsec = _.lines()
        else: elsec = None
        
        return _.o('if', expr, 'then', ifc, 'elif', elifs, 'else', elsec)
    
    def forr(_):
        _.tokr("$for ")
        _.lock()
        v = _.setabler()
        _.tokr(" in ")
        g = _.exprr()
        _.tokr(":")
        l = _.lines()

        if _.tokq(_.curws+_.curind+'$else:'): elsec = _.lines()
        else: elsec = None
            
        return _.o('for', v, 'in', g, 'do', l, 'else', elsec)
    
    def whiler(_):
        _.tokr('$while ')
        _.lock()
        v = _.exprr()
        _.tokr(":")
        l = _.lines()
        
        if _.tokq(_.curws+_.curind+'$else:'): elsec = _.lines()
        else: elsec = None
        
        return _.o('while', v, 'do', l, 'else', elsec)
    
    def assignr(_):
        _.tokr('$ ')
        assign = _.varr()[1] # NOTE: setable
        _.tokr(' = ')
        expr = _.exprr()
        _.tokr('\n')
        
        return _.o('assign', assign, 'expr', expr)
        
    def commentr(_):
        _.tokr('$#')
        _.lock()
        while _.c() != '\n': pass
        return ('comment', None)
        
    def varr(_):
        return _.o('var', _.rer(r_var))
    
    def setabler(_):
        out = [_.varr()] #@@ not quite right
        while _.tokq(', '):
             out.append(_.varr())
        return out
    
    def getabler(_):
        parens = bool(_.tokq('('))
        
        #var ["." var]+
        n = _.varr()
        while 1:
            if _.tokq('.'):
                v = _.varq()
                if not v:
                    _.p -= 1 # get rid of the '.'
                else:
                    n = ('getattr', n, v)
            elif _.tokq('('):
                args = []
                kw = []
                x = _.exprq()
                while x:
                    if _.tokq('='):
                        v = _.exprr()
                        kw.append((x[1], v))
                    else: 
                        args.append(x)
                    x = _.tokq(', ') and _.exprq()
                _.tokr(')')
                n = ('call', n, 'args', args, 'kw', kw)
            else:
                break
        
        if parens: _.tokr(')')
        return _.o('getable', n, 'filter', filter)
    
    def lines(_, start=False):
        """
        This function gets called from two places:
          1. at the start, where it's matching the document itself
          2. after any command, where it matches one line or an indented block
        """
        o = []
        if not start: # try to match just one line
            singleline = _.tokq(' ') and _.lineq()
            if singleline:
                return [singleline]
            else:
                _.rer(' *') #@@slurp space?
                _.tokr('\n')
                oldind = _.curind
                _.curind += '    '
        while 1:
            oldws = _.curws
            t = _.tokq(oldws + _.curind)
            if not t: break
            
            _.curws += _.ws()
            x = t and (
              _.setq() or 
              _.ifq() or 
              _.forq() or 
              _.whileq() or 
              _.assignq() or
              _.commentq() or
              _.lineq())
            _.curws = oldws
            if not x: break
            else: o.append(x)

        if not start: _.curind = oldind
        return o
    
    def liner(_):
        out = []
        o = _.curws
        while 1:
            c = _.c()
            _.lock()
            if c == '\n': _.p -= 1; break
            if c == '$':
                if _.lookbehind('\\$'):
                    o = o[:-1] + c
                else:
                    filter = not bool(_.tokq(':'))
                    
                    if _.tokq('{'):
                        out.append(o)
                        out.append(_.o('var', _.exprr(), 'filter', filter))
                        _.tokr('}')
                        o = ''
                    else:
                        g = _.getableq()
                        if g: 
                            out.append(o)
                            out.append(_.o('var', _.o('expr', g), 'filter', filter))
                            o = ''
                        else:
                            o += c
            else:
                o += c
        _.tokr('\n')
        if not _.lookbehind('\\\n'):
            o += '\n'
        else:
            o = o[:-1]
        out.append(o)
        return _.o('line', out)
    
    def onethingr(_):
        if _.tokq('('):
            o = _.exprr()
            _.tokq(')')
        else:
            o = (
              _.getableq() or 
              _.req('[0-9]+') or 
              _.req('"[^"]*"') or #@@ no support for escapes
              _.req("'[^']*'"))
        if o: return o
        else: _.Error('expression')

    def exprr(_):
        x = _.onethingr()
        if _.tokq(' '):
            clause = _.ltokr('is not', 'is', '==', '!=', '<', '>', 'and', 'or')
            _.tokr(' ')
            y = _.onethingr()
            x = ('test', x, clause, y)
            
        return _.o('expr', x)

def itemize(item):
    return storage(dict(group(item, 2)))

class Stowage(storage):
    def __str__(self): return self.get('_str')

class WTF(AssertionError): pass

class Handle:
    def __init__(self, parsetree, **kw):
        self.parsetree = parsetree
        for (k, v) in kw.iteritems(): setattr(self, k, v)    
    
    def h(self, item):
        return getattr(self, 'h_'+item[0])(itemize(item))
            
class Fill(Handle):
    builtins = {'None':None, 'False':False, 'True': True}
    def filter(self, text):
        if text is None: return ''
        else: return str(text)
        # later: can do stuff like WebSafe
    
    def h_expr(self, item):
        assert item[0] == 'expr'
        item = item[1]
        if isinstance(item, str) and item.isdigit():
            item = int(item)
        elif isinstance(item, str) and item[0] in ['"', "'"]:
            item = item[1:-1]
        elif item[0] == 'getable':
            item = self.h_getable(item[1])
        elif item[0] == 'test':
            item = self.h_test(*item[1:])
        else:
            raise WTF, item
        return item
    
    def h_onething(self, x):
        if x[0] != 'expr':
            x = ('expr', x)
        return self.h_expr(x)
        
    def h_test(self, ox, clause, oy):
        # for short-circuiting to work, we can't eval these here
        x, y = lambda: self.h_onething(ox), lambda: self.h_onething(oy)
        if clause == 'is':
            return x() is y()
        elif clause == 'is not':
            return x() is not y()
        elif clause == '==':
            return x() == y()
        elif clause == '!=':
            return x() != y()
        elif clause == '>':
            return x() > y()
        elif clause == '<':
            return x() < y()
        elif clause == 'and':
            return x() and y()
        elif clause == 'or':
            return x() or y()
        else:
            raise WTF, 'clause ' + clause
    
    def h_var(self, i):
        assert i[0] == 'var'
        try:
            v = i[1]
            if v in self.builtins:
                return self.builtins[v]
            else:
                return self.d[v]
        except KeyError:
            i = itemize(i)
            raise NameError, 'could not find %s (line %s)' % (repr(i.var), i.lineno)
    
    def h_getable(self, i):
        if i[0] == 'expr':
            out = self.h_expr(i)
        elif i[0] == 'var':
            out = self.h_var(i)
        elif i[0] == 'getattr':
            what, attr = i[1:]
            assert attr[0] == 'var'
            out = getattr(self.h_getable(what), attr[1])
        elif i[0] == 'call':
            i = itemize(i)
            call = self.h_getable(i.call)
            args = [self.h_getable(x) for x in i.args]
            kw = dict([(x, self.h_getable(y)) for (x, y) in i.kw])
            out = call(*args, **kw)
        else:
            raise WTF, i
        return out
        
    def h_line(self, i):
        out = ''
        for x in i.line:
            if isinstance(x, str):
                out += x
            elif x[0] == 'var':
                x = itemize(x)
                o = self.h_expr(x.var)
                if x.filter: o = self.filter(o)
                out += o
            elif x[0] == 'ex':
                raise WTF, x
        return out
    
    def h_lines(self, lines):
        if lines is None: return ''
        return ''.join([self.h(x) or '' for x in lines])
    
    def h_set(self, i):
        assert i.set[0] == 'var'
        self.output[i.set[1]] = self.h_lines(i.body)

    def h_if(self, i):
        expr = self.h_expr(i['if'])
        if expr: do = i['then']
        else:
            do = None
            for e in i['elif']:
                e = itemize(e)
                expr = self.h_expr(e['expr'])
                if expr:
                    do = e['code']
                    break
                
            if not do: do = i['else']
        return self.h_lines(do)
        
    def h_for(self, i):
        out = ''
        assert i['in'][0] == 'expr'
        invar = self.h_expr(i['in'])
        forvar = i['for']
        if invar:
            for nv in invar:
                if len(forvar) == 1:
                    fv = forvar[0]
                    assert fv[0] == 'var'
                    self.d[fv[1]] = nv # same (lack of) scoping as Python
                else:
                    for x, y in zip(forvar, nv):
                        assert x[0] == 'var'
                        self.d[x[1]] = y
                
                out += self.h_lines(i['do'])
        else:
            if i['else']:
                out += self.h_lines(i['else'])
        return out
    
    def h_while(self, i):
        out = ''
        expr = self.h_expr(i['while'])
        if not expr: return self.h_lines(i['else'])
        c = 0
        while expr:
            c += 1
            if c >= MAX_ITERS:
                raise RuntimeError, 'too many while-loop iterations (line %s)' % i.lineno
            out += self.h_lines(i['do'])
            expr = self.h_expr(i['while'])
        return out

    def h_assign(self, i):
        self.d[i.assign] = self.h_expr(i.expr)

    def h_comment(self, i): pass
    
    def go(self):
        self.output = Stowage()
        self.output._str = ''
        for item in self.parsetree:
            self.output._str += self.h(item) or ''
        return self.output

Required = object()
class Template:
    globals = {}
    def __init__(self, text, filter=None):
        self.filter = filter
        if not text.endswith('\n'): text += '\n'
        header, tree = TemplateParser(text).go()
        self.tree = tree
        if header:
            assert header[0] == 'defwith'
            self.args, kw = header[1:3]
            self.kwargs = []
            f = Fill(self.tree)
            for var, valexpr in kw:
                self.kwargs.append((var, f.h_expr(valexpr)))
        else:
            self.args, self.kwargs = (), {}
    
    def __call__(self, *a, **kw):
        d = self.globals.copy()
        d.update(self._parseargs(a, kw))
        f = Fill(self.tree, d=d)
        if self.filter: f.filter = self.filter
        return f.go()
    
    def _parseargs(self, inargs, inkwargs):
        # difference from Python:
        #   no error on setting a keyword arg twice
        d = {}
        for arg in self.args:
            d[arg] = Required
        for kw, val in self.kwargs:
            d[kw] = val

        for n, val in enumerate(inargs):
            if n < len(self.args):
                d[self.args[n]] = val
            elif n < len(self.args)+len(self.kwargs):
                kw = self.kwargs[n - len(self.args)][0]
                d[kw] = val

        for kw, val in inkwargs.iteritems():
            d[kw] = val

        unset = []
        for k, v in d.iteritems():
            if v is Required:
                unset.append(k)
        if unset:
            raise TypeError, 'values for %s are required' % unset 

        return d

def websafe(val):
    if val is None: return ''
    return htmlquote(str(val))