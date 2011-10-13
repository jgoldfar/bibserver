import json, urllib2
from copy import deepcopy
import operator, unicodedata
import bibserver.dao
import bibserver.config
import re

class IOManager(object):
    def __init__(self, results, args, user):
        self.results = results
        self.user = user
        self.config = bibserver.config.Config()
        self.args = args if args is not None else {}
        self.facet_fields = {}
        for facet,data in self.results['facets'].items():
            self.facet_fields[facet.replace(self.config.facet_field,'')] = data["terms"]

    def get_q(self):
        return self.args.get('q','')
    
    def get_safe_terms_object(self):
        terms = {}
        for term in self.args["terms"]:
            if term.replace(self.config.facet_field,'') not in self.args["path"]:
                theterm = '['
                for i in self.args['terms'][term]:
                    theterm += '"' + i + '",'
                theterm = theterm[:-1]
                theterm += ']'
                terms[term.replace(self.config.facet_field,'')] = theterm
        return terms    

    def get_path_params(self,myargs):
        param = '/' + myargs["path"] + '?' if (myargs["path"] != '') else self.config.base_url + '?'
        if 'q' in myargs:
            param += 'q=' + myargs['q'] + '&'
        if 'terms' in myargs:
            for term in myargs['terms']:
                if term.replace(self.config.facet_field,'') not in self.args["path"]:
                    val = '[' + ",".join(urllib2.quote('"{0}"'.format(i.encode('utf-8'))) for i in myargs['terms'][term]) + ']'
                    param += term.replace(self.config.facet_field,'') + '=' + val + '&'
        if 'showkeys' in myargs:
            param += 'showkeys=' + myargs['showkeys'] + '&'
        return param

    def get_add_url(self, field, value):
        myargs = deepcopy(self.args)
        field += self.config.facet_field
        if myargs['terms'].has_key(field):
            if value not in myargs['terms'][field]:
                myargs['terms'][field].append(value)
        else:
            myargs['terms'][field] = [value]
        return self.get_path_params(myargs)
        
    def get_delete_url(self, field, value=None):
        myargs = deepcopy(self.args)
        if value is not None:
            field += self.config.facet_field
            myargs['terms'][field].remove(value)
            if len(myargs['terms'][field]) == 0:
                del myargs['terms'][field]
        else:
            del myargs['terms'][field]
        return self.get_path_params(myargs)


    def in_args(self, facet, value):
        return self.args['terms'].has_key(facet + self.config.facet_field) and value in self.args['terms'][facet + self.config.facet_field]
            
    def get_result_display(self,counter):
        '''use the result_display object as a template for search results'''
        display = self.config.result_display
        output = ""
        if not display:
            return output

        for item in display:
            line = ""
            for pobj in item:
                if 'key' in pobj:
                    keydisp = self.get_str(self.set()[counter],pobj['key'])
                    if keydisp:
                        try:
                            keydisp = unichr(keydisp)
                        except:
                            pass
                        line += pobj.get('pre','') + keydisp + pobj.get('post','') + " "
                if 'default' in pobj:
                    line += pobj.get('default','') + " "
            if line:
                output += line.strip().strip(",") + "<br />"

        if self.showkeys():
            output += '<table>'
            keys = [i for i in self.showkeys().split(',')]
            for key in keys:
                out = self.get_str(self.set()[counter],key)
                if out:
                    output += '<tr><td><strong>' + key + '</strong>: ' + out + '</td></tr>'
            output += '</table>'
        return output
        
    '''get all currently available keys in ES'''
    def get_keys(self):
        return ""
    
    '''get keys to show on results'''
    def showkeys(self):
        return self.args.get('showkeys',"")

    def get_facet_fields(self):
        return [i['key'] for i in self.config.facet_fields]

    def get_rpp_options(self):
        return self.config.results_per_page_options

    def get_sort_fields(self):
        return self.config.sort_fields

    def numFound(self):
        return int(self.results['hits']['total'])

    def page_size(self):
        return int(self.args.get("size",10))

    def paging_range(self):
        return ( self.numFound() / self.page_size() ) + 1

    def sorted_by(self):
        if "sort" in self.args:
            return self.args["sort"].keys()[0].replace(self.config.facet_field,"")
        return ""

    def sort_order(self):
        if "sort" in self.args:
            return self.args["sort"][self.args["sort"].keys()[0]]["order"]
        return ""
        
    def start(self):
        return int(self.args.get('start',0))

    def set(self):
        '''Return list of search result items'''
        return [rec['_source'] for rec in self.results['hits']['hits']]


    def get_str(self, result, field, raw=False):
        res = result.get(field,"")
        if not res:
            return ""
        if self.config.display_value_functions.has_key(field) and not raw:
            d = self.config.display_value_functions[field]
            func_name = d.keys()[0]
            args = d[func_name]
            args["field"] = field
            if self.user:
                args["user"] = self.user
            args["path"] = self.args["path"]
            func = globals()[func_name]
            return func(res, args)
        else:
            if isinstance(res,list):
                return ','.join(res)
        return res
        
    def get_meta(self):
        meta = ""
        if self.user:
            coll = self.args['path'].replace(self.user+'/','')
            res = bibserver.dao.Collection.query(terms={'slug':[coll]})
            if len(res['hits']['hits']) > 0:
                rec = res['hits']['hits'][0]['_source']
                meta = '<p><a href="/'
                meta += self.args['path'] + '.json?size=' + str(rec['records'])
                meta += '">Download this collection</a><br />'
                meta += 'This collection was created by <a href="/account/' + rec['owner'] + '">' + rec['owner'] + '</a><br />'
                if "source" in rec:
                    meta += 'The source of this collection is <a href="'
                    meta += rec["source"] + '">' + rec["source"] + '</a>.<br /> '
                if "modified" in rec:
                    meta += 'This collection was last updated on ' + rec["modified"] + '. '
                if "source" in rec:
                    meta += '<br />If changes have been made to the source file since then, '
                    meta += '<a href="/upload?source=' + rec["source"] + '&collection=' + rec["slug"]
                    meta += '">refresh this collection</a>.'
                #meta += '<br /><a class="delete_link" href="/query?delete=true&q=collection.exact:%22' + rec["slug"] + '%22">Delete this collection</a></p>'
            return meta
        else:
            return meta
        



# the following methods can be called by get_field_display
# to perform various functions upon a field for display

def authorify(vals, dict):
    return ' and '.join(['<a class="author_name" alt="search for ' + i + '" title="search for ' + i + '" ' + 'href="/search?q=' + i + '">' + i + '</a>' for i in vals])

def wrap(value, dict):
    return dict['start'] + value + dict['end']
    
def doiify(value, dict):
    # dois may start with:
    # 10. - prefix http://dx.doi.org/
    # doi: - strip doi: and replace with http://dx.doi.org/
    # http://dx.doi.org/ already done, just linkify
    resolver = dict.get("resolver", "http://dx.doi.org/")
    link = None
    if value.startswith("10."):
        link = resolver + value
    elif value.startswith("doi:"):
        link = resolver + value[4:]
    elif value.startswith("http://"):
        link = value
    
    if link is not None:
        return '<a href="' + link + '">' + value + '</a>'
    else:
        return value

def searchify(value, dict):
    # for the given value, make it a link to a search of the value
    return '<a href="?q=' + value + '" alt="search for ' + value + '" title="search for ' + value + '">' + value + '</a>'

def implicify(value, dict):
    # for the given value, make it a link to an implicit facet URL
    return '<a href="/' + dict.get("field") + "/" + value + '" alt="go to ' + dict.get("field") + " - "  + value + '" title="go to ' + dict.get("field") + " - "  + value + '">' + value + '</a>'

def collectionify(value, dict):
    # for the given value, make it a link to a collection facet URL
    res = bibserver.dao.Collection.query(q='slug:"'+value+'"')['hits']['hits']
    if len(res) != 0:
        owner = res[0]['_source']['owner']
        if not dict["path"].startswith(owner+'/'):
            return '<a href="/' + owner + "/" + value + '" alt="go to collection '  + value + '" title="go to collection '  + value + '">' + value + '</a>'
        else:
            return False
    else:
        return False

def personify(value, dict):
    # for the given value, make it a link to a person URL
    return '<a href="/person/' + value + '" alt="go to '  + value + ' record" title="go to ' + value + ' record">' + value + '</a>'

def _get_location_pairs(message, start_sub, finish_sub):
    idx = 0
    pairs = []
    while message.find(start_sub, idx) > -1:
        si = message.find(start_sub, idx)
        sf = message.find(finish_sub, si)
        pairs.append((si, sf))
        idx = sf
    return pairs

def _create_url(url):
    return "<a href=\"%(url)s\">%(url)s</a>" % {"url" : url}

def linkify(nm, args):
    parts = _get_location_pairs(nm, "http://", " ")
    
    # read into a sortable dictionary
    dict = {}
    for (s, f) in parts:
        dict[s] = f
    
    # sort the starting points
    keys = dict.keys()
    keys.sort()
    
    # determine the splitting points
    split_at = [0]
    for s in keys:
        f = dict.get(s)
        split_at.append(s)
        split_at.append(f)
    
    # turn the splitting points into pairs
    pairs = []
    for i in range(0, len(split_at)):
        if split_at[i] == -1:
            break
        if i + 1 >= len(split_at):
            end = len(nm)
        elif split_at[i+1] == -1:
            end = len(nm)
        else:
            end = split_at[i+1]
        pair = (split_at[i], end)
        pairs.append(pair)
    
    frags = []
    for s, f in pairs:
        frags.append(nm[s:f])
    
    for i in range(len(frags)):
        if frags[i].startswith("http://"):
            frags[i] = _create_url(frags[i])
    
    message = "".join(frags)
    return message

def bibsoup_links(vals,dict):
    links = ""
    for url in vals:
        links += '<a href="' + url['url'] + '">'
        if 'anchor' in url:
            links += url['anchor']
        else:
            links += url['url']
        if 'format' in url:
            links += ' (' + url['format'] + ') '
        links += '</a> | '
    return links.strip(' | ')
