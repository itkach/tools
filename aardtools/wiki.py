import logging
logging.basicConfig()
import functools 
import re

from lxml import etree
import simplejson

from mwlib import uparser, xhtmlwriter
from mwlib.log import Log
Log.logfile = None

import mwaardwriter

tojson = functools.partial(simplejson.dumps, ensure_ascii=False)

NS = '{http://www.mediawiki.org/xml/export-0.3/}'

class WikiParser():
    
    def __init__(self, templatedb, consumer):
        self.templatedb = templatedb
        self.consumer = consumer
        self.redirect_re = re.compile(r"\[\[(.*?)\]\]")
        self.article_count = 0
        
    def parse(self, f):
        self.consumer.add_metadata('article_format', 'json')
        for event, element in etree.iterparse(f):
            if element.tag == NS+'sitename':                
                self.consumer.add_metadata('title', element.text)
                element.clear()
                
            elif element.tag == NS+'base':
                m = re.compile(r"http://(.*?)\.wik").match(element.text)
                if m:
                    self.consumer.add_metadata("index_language", m.group(1))
                    self.consumer.add_metadata("article_language", m.group(1))
                                    
            elif element.tag == NS+'page':
                
                for child in element.iter(NS+'text'):
                    text = child.text
                
                if not text:
                    continue
                
                for child in element.iter(NS+'title'):
                    title = child.text

                if text.lstrip().lower().startswith("#redirect"): 
                    m = self.redirect_re.search(text)
                    if m:
                        redirect = m.group(1)
                        redirect = redirect.replace("_", " ")
                        meta = {u'redirect': redirect}
                        self.consumer.add_article(title, tojson(('', [], meta)))
                    continue
    
                mwobject = uparser.parseString(title=title, 
                                               raw=text, 
                                               wikidb=self.templatedb)
                xhtmlwriter.preprocess(mwobject)
                text, tags = mwaardwriter.convert(mwobject)
                self.consumer.add_article(title, tojson((text.rstrip(), 
                                                         tags, {})))
                self.article_count += 1
                element.clear()
        self.consumer.add_metadata("self.article_count", self.article_count)        