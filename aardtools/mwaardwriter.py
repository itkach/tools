import functools
import logging
from collections import defaultdict

EXCLUDE_TABLE_CLASSES = set(('navbox', 'collapsible', 'autocollapse'))

def convert(obj):
    w = MWAardWriter()
    text, tags = w.txt(obj)
    return text, tags

def newline(func):
    def f(*args, **kwargs):
        txt, tags = func(*args, **kwargs)
        if txt and not txt.endswith(u'\n'):
            txt += u'\n'        
        return txt, tags
    f.__name__ = func.__name__
    f.__doc__ = func.__doc__
    return f

class Cell(object):
    
    def __init__(self, text, tags=None, colspan=1, rowspan=1):
        self.text = text
        self.colspan = colspan
        self.rowspan = rowspan
        self.tags = [] if tags is None else tags

class Row(list):
    def __init__(self, attributes=None):
        self.attributes = attributes

class MWAardWriter(object):

    def __init__(self):
        self.refgroups = defaultdict(list)        
        self.errors = []
        self.languagelinks = []
        self.categorylinks = []        
        self.current_list_number = 0
        self.current_tables = []
        
    def _Text(self, obj):
        return obj.caption, []

    @newline
    def _ItemList(self, obj):
        self.current_list_number = 0
        return self.process_children(obj)
    
    @newline
    def _Item(self, obj):
        txt = u''        
        if (obj.parent.numbered):
            self.current_list_number += 1
            txt += u'%d. ' % self.current_list_number
        else:
            txt += u'\u2022 '
        return self.process_children(obj, txt)        
    
    @newline
    def _Paragraph(self, obj):
        txt, tags = self.process_children(obj)
        tags.append(maketag(u'p', txt, obj.attributes))
        return txt, tags        
    
    @newline
    def _Section(self, obj):
        level = 2 + obj.getLevel() # starting with h2
        h = u'h%d' % level
        txt, tags = self.txt(obj.children[0])
        tags.append(maketag(h, txt))
        txt += u'\n'
        obj.children = obj.children[1:]
        return self.process_children(obj, txt, tags)

    @newline
    def _Chapter(self, obj):
        txt = obj.caption
        tags = [maketag(u'h1', txt)]
        return txt, tags

    @newline
    def _Caption(self, obj):
        txt = obj.caption
        tags = [maketag(u'strong', txt)]
        return txt, tags
    
    def _CategoryLink(self, obj):
        self.categorylinks.append(obj.target)
        return u'', []

    def _LangLink(self, obj):
        self.languagelinks.append((obj.namespace, obj.target))
        return u'', []
    
    def _ArticleLink(self, obj):
        txt, tags = self.process_children(obj)
        if not txt:
            txt = obj.caption
            print 'Article ', txt.encode('utf8')
        tags.append(maketag(u'a', txt, {u'href':obj.target}))
        return txt, tags
    
    _InterwikiLink = _ArticleLink       
    
    def _NamedURL(self, obj):
        txt, tags = self.process_children(obj)
        if not txt:
            txt = obj.caption        
        tags.append(maketag(u'a', txt, {u'href':obj.caption}))
        return txt, tags

    def _URL(self, obj):
        txt, tags = self.process_children(obj)
        if not txt:
            txt = obj.caption
        tags.append(maketag(u'a', txt, {u'href':obj.caption}))
        return txt, tags
    
    def _Style(self, obj):
        txt, tags = self.process_children(obj)
        if obj.caption == "''":
            tags.append(maketag(u'i', txt))
        elif obj.caption == "'''":
            tags.append(maketag(u'b', txt))
        elif obj.caption == ";":
            tags.append(maketag(u'tt', txt))            
        return tags                

    def _TagNode(self, obj):
        txt, tags = self.process_children(obj)
        tagname = obj.caption
        tags.append(maketag(tagname, txt, obj.attributes))
        return txt, tags        

    def _Node(self, obj):
        txt, tags = self.process_children(obj)
        tagname = obj._tag if hasattr(obj, '_tag') else obj.caption
        if tagname:
            tags.append(maketag(tagname, txt, obj.attributes))
        return txt, tags        
    
    def _ImageLink(self, obj):
        return '', []
    
    def _BreakingReturn(self, obj):
        return u'\n', []
    
    def _Generic(self, obj):
        txt, tags = self.process_children(obj)
        tagname = obj._tag
        tags.append(maketag(tagname, txt, obj.attributes))
        return txt, tags    
    
    _Emphasized = _Strong = _Small = _Big = _Cite = _Sub = _Sup = _Generic
    
    _Div = newline(_Generic)
    
    def add_ref(self, obj):
        name = obj.attributes.get(u'name', '')        
        group = obj.attributes.get(u'group', '')
        
        references = self.refgroups[group]
        
        refid = None
        
        if name:        
            existing = [r for r in references 
                        if name == r.attributes.get(u'name', '')]
            if existing:
                refid = references.index(existing[0])
                
        if refid is None:        
            references.append(obj)
            refid = len(references)
        return refid, name, group
            
    def _Reference(self, obj):        
        refid, name, group = self.add_ref(obj)
        refidstr = unicode(refid)
        txt = u'%s %s' % (group, refidstr)
        txt = u'[%s]' % txt.strip()
        return txt, [maketag(u'ref', txt, {u'id': refidstr, 
                                           u'group': group})]
    
    @newline
    def _ReferenceList(self, obj):
        group = obj.attributes.get(u'group', '')
        tags = []
        txt = u''
        for i, refobj in enumerate(self.refgroups[group]):            
            start = len(txt)
            refid = unicode(i+1)
            refidtxt = u'[%s]' % refid
            txt += refidtxt + u' '
            tags.append(maketag(u'b', refidtxt, start=start))
            txt, tags = self.process_children(refobj, txt, tags)
            tags.append(maketag(u'note', txt,  {u'id': refid, 
                                                u'group': group}, 
                                                start=start))                        
            txt += u'\n'
        del self.refgroups[group]
        return txt, tags            
    
    def _Article(self, a):
        # add article name as first section heading
        txt = a.caption
        logging.debug('Article %s', txt.encode('utf8'))
        tags = [maketag(u'h1', txt)]
        txt += u'\n'
        return self.process_children(a, txt, tags)        
    
    def _Cell(self, obj):
        current_table, current_row = self.current_tables[-1]
        if current_row is None:            
            logging.warn("Can't add cell outside of row")
        else:                       
            txt, tags = self.process_children(obj)
            #txt = txt.replace('\n', ' ')
            txt = txt.replace('\t', ' ')
            colspan = obj.colspan
            rowspan = obj.rowspan
            #tags.append(maketag(u'td', obj.attributes))
            current_row.append(Cell(txt, tags, colspan, rowspan))
        return '', []

    def _Row(self, obj):            
        current_table, current_row = self.current_tables[-1]
        if current_row is not None:
            logging.error('Processing row is already in progress')
        else:            
            self.current_tables[-1] = (current_table, Row())              
            self.process_children(obj)
            current_table, current_row = self.current_tables[-1]
            current_row.attributes = obj.attributes
            current_table.append(current_row)
            self.current_tables[-1] = (current_table, None)                
        return '', []
    
    @newline    
    def _Table(self, obj):
        tableclasses = obj.attributes.get('class', '').split()
        if any((tableclass in EXCLUDE_TABLE_CLASSES 
                for tableclass in tableclasses)):
            return '', []
        
        self.current_tables.append(([], None))
        if obj.caption:
            logging.debug('Table %s', obj.caption.encode('utf8'))
        tabletext, tags = self.process_children(obj)
        current_table, current_row = self.current_tables.pop()
        if current_table:
            txt = u' '
            tabletext, tags, tabs = self.maketable(current_table, tabletext, tags)
            tags = [maketag('tbl', txt, {u'text': tabletext, 
                                         u'tags': tags,
                                         u'tabs': tabs,
                                         })]
            return txt, tags
        else:
            caption = obj.caption if obj.caption else u'' 
            logging.warn('Table %s has no data, skipping', 
                         caption.encode('utf8'))
            return '', []
    
    def maketable(self, data, tabletext=u'', tabletags=None):
        newdata = []
        rowspanmap = defaultdict(int)
        for i, row in enumerate(data):
            newrow = []
            j = 0
            for cell in row:
                while rowspanmap[j] > 0:
                    rowspanmap[j] = rowspanmap[j] - 1
                    j += 1
                    newrow.append(Cell(''))
                rowspan = cell.rowspan
                for k in range(j, j+cell.colspan):
                    rowspanmap[k] = rowspan - 1
                cell.rowspan = 1                    
                newrow.append(cell)
                j += cell.colspan
            newdata.append(newrow)

        newdata2 = []
        for i, row in enumerate(newdata):
            linecounts = [len(cell.text.splitlines()) for cell in row]
            count = max(linecounts) if linecounts else 0
            if count > 1:
                newrows = [[] for k in range(count)]
                for cell in row:
                    lines = cell.text.splitlines()
                    while len(lines) < count:
                        lines.append('')
                    
                    linelens = [len(line) for line in lines]
                    cutpoints = []
                    runningsum = 0
                    for linelen in linelens:
                        runningsum += (linelen + 1) # add one to take into account newline char
                        cutpoints.append(runningsum)
                    print cutpoints
                    
                    linetags=[[] for k in range(count)]    
                    for tag in cell.tags:
                        print 'Cell tag', tag
                        print 'Cutpoints', cutpoints
                        start = tag[1]
                        end = tag[2]
                        
                        prevcutpoint = 0
                        for c, cutpoint in enumerate(cutpoints):
                            if prevcutpoint <= start < cutpoint:
                                newstart = start - prevcutpoint
                                newtag = list(tag)
                                newtag[1] = newstart
                                newtag[2] = cutpoint - 1 if end > cutpoint else end - prevcutpoint
                                print 'Line %d, adding tag %s' % (c, newtag)        
                                linetags[c].append(newtag)                                                
                                if end > cutpoint:
                                    start = cutpoint                                    
                                else:
                                    break         
                            prevcutpoint = cutpoint                                                       
                    
                    for j, line in enumerate(lines):
                        rowspan = 1 if j < count - 1 else cell.rowspan
                        print 'Line: %s, tags: %s' % (line.encode('utf8'), linetags[j]) 
                        newcell = Cell(line,  linetags[j], cell.colspan, cell.rowspan)
                        newrows[j].append(newcell)                                        
                newdata2 += newrows
            else:
                newdata2.append(row)

        data = newdata2

        text = tabletext
        tags = [] if tabletags is None else tabletags
        rowspanmap = defaultdict(int)
        for i, row in enumerate(data):
            start = len(text)
            j = 0
            for cell in row:
                offset = len(text)
                text += cell.text
                tags += [self.apply_offset(tag, offset) for tag in cell.tags]
                text += '\t'        
            text += u'\n'
            end = len(text)
            tags.append((u'row', start, end))
        
        tabcount = max([sum(cell.colspan for cell in row) for row in data]) 
        globaltabs = [0 for i in range(tabcount)]

        lenmatrix = []
        
        def zero(globaltabs, i):
            return 0
        
        for i, row in enumerate(data):
            rowentry = []
            lenmatrix.append(rowentry)
            for cell in row:
                for j in range(cell.colspan):
                    if j == cell.colspan - 1:
                        def lencontrib(text, colspan, globaltabs, n):
                            contrib = len(text) + 1
                            for k in range(colspan - 1):
                                contrib -= globaltabs[n-k-1]
                            return contrib
                        l = functools.partial(lencontrib, cell.text, cell.colspan)
                    else:
                        l = zero                    
                    rowentry.append(l)
            if len(rowentry) < tabcount:
                logging.warn('Bad table, expected %d total column span, got only %d', tabcount, len(rowentry))
                while len(rowentry) < tabcount:
                    rowentry.append(zero)                                                                            

        for i in range(len(globaltabs)):            
            cell_lengths = [row[i](globaltabs, i) for row in lenmatrix]
            globaltabs[i] = max(cell_lengths)

        runningsum = 0
        for i, rawtab in enumerate(globaltabs):
            runningsum += rawtab
            globaltabs[i] = runningsum
                
        tabs = {'': globaltabs}
        
        for i, row in enumerate(data):
            if any([cell.colspan > 1 for cell in row]):                
                rowtabs = []
                tabs[i] = rowtabs
                j=0                 
                for cell in row:
                    pos = globaltabs[j+cell.colspan - 1]
                    rowtabs.append(pos)
                    j += cell.colspan
                
        return text, tags, tabs
        
    def apply_offset(self, tag, offset):
        mtag = list(tag)
        mtag[1] += offset
        mtag[2] += offset
        return tuple(mtag)
        
    def txt(self, obj):
        m = "_" + obj.__class__.__name__
        m = getattr(self, m, None)
        if m: # find handler
            return m(obj)
        else:
            logging.debug('No handler for %s, write children', obj)
            return self.process_children(obj)
                
    def process_children(self, obj, txt=u'', tags=None):
        if tags is None:
            tags = []
        else:
            tags = tags[:]
        for c in obj:
            ctxt, ctags = self.txt(c)
            txtlen = len(txt)
            tags += [self.apply_offset(ctag, txtlen) for ctag in ctags]
            txt += ctxt            
        logging.debug('Processed children for %s, returning %s with tags %s', 
                      obj, txt, tags)
        return txt, tags                

def maketag(name, txt, attrs=None, start=0):
    end = start + len(txt)
    return (name, start, end, attrs) if attrs else (name, start, end) 
