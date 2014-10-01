## consumer for DataONE SOLR search API

import re
from lxml import etree
from xml.etree import ElementTree
import requests
from nameparser import HumanName

from dateutil.parser import *

from scrapi.linter import lint
from scrapi.linter.document import RawDocument, NormalizedDocument

NAME = "DataONE"

def consume(days_back=1):
    doc =  get_response(1, days_back)
    rows = doc.xpath("//result/@numFound")[0]
    doc = get_response(rows, days_back)
    records = doc.xpath('//doc')
    
    xml_list = []
    for record in records:
        doc_id = record.xpath("str[@name='id']")[0].text
        record = ElementTree.tostring(record)
        record = '<?xml version="1.0" encoding="UTF-8"?>\n' + record
        xml_list.append(RawDocument({
                    'doc': record,
                    'source': NAME,
                    'docID': doc_id,
                    'filetype': 'xml'
                }))

    return xml_list

def get_response(rows, days_back):
    ''' helper function to get a response from the DataONE
    API, with the specified number of rows.
    Returns an etree element with results '''
    url = 'https://cn.dataone.org/cn/v1/query/solr/?q=dateModified:[NOW-{0}DAY TO *]&rows='.format(days_back) + str(rows)
    data = requests.get(url)
    doc =  etree.XML(data.content)
    return doc

def get_properties(doc):
    properties = { 
        'author': (doc.xpath("str[@name='author']/node()") or [''])[0],
        'authorGivenName': (doc.xpath("str[@name='authorGivenName']/node()") or [''])[0],
        'authorSurName': (doc.xpath("str[@name='authorSurName']/node()") or [''])[0],
        'authoritativeMN' : (doc.xpath("str[@name='authoritativeMN']/node()") or [''])[0],
        'checksum' : (doc.xpath("str[@name='checksum']/node()") or [''])[0],
        'checksumAlgorithm' : (doc.xpath("str[@name='checksumAlgorithm']/node()") or [''])[0],
        'dataUrl': (doc.xpath("str[@name='dataUrl']/node()") or [''])[0],
        'datasource': (doc.xpath("str[@name='datasource']/node()") or [''])[0],

        'dateModified': (doc.xpath("date[@name='dateModified']/node()") or [''])[0],
        'datePublished': (doc.xpath("date[@name='datePublished']/node()") or [''])[0],
        'dateUploaded': (doc.xpath("date[@name='dateUploaded']/node()") or [''])[0],
        'pubDate': (doc.xpath("date[@name='pubDate']/node()") or [''])[0],
        'updateDate': (doc.xpath("date[@name='updateDate']/node()") or [''])[0],

        'fileID': (doc.xpath("str[@name='fileID']/node()") or [''])[0],
        'formatId': (doc.xpath("str[@name='formatId']/node()") or [''])[0],
        'formatType': (doc.xpath("str[@name='formatType']/node()") or [''])[0],

        'identifier': (doc.xpath("str[@name='identifier']/node()") or [''])[0],

        'investigator': doc.xpath("arr[@name='investigator']/str/node()"),
        'origin': doc.xpath("arr[@name='origin']/str/node()"),

        'isPublic': (doc.xpath("bool[@name='isPublic']/node()") or [''])[0],
        'readPermission': doc.xpath("arr[@name='readPermission']/str/node()"),
        'replicaMN': doc.xpath("arr[@name='replicaMN']/str/node()"),
        'replicaVerifiedDate': doc.xpath("arr[@name='replicaVerifiedDate']/date/node()"),
        'replicationAllowed': (doc.xpath("bool[@name='replicationAllowed']/node()") or [''])[0],
        'numberReplicas': (doc.xpath("int[@name='numberReplicas']/node()") or [''])[0],
        'preferredReplicationMN': doc.xpath("arr[@name='preferredReplicationMN']/str/node()"),

        'resourceMap': doc.xpath("arr[@name='resourceMap']/str/node()"),

        'rightsHolder': (doc.xpath("str[@name='rightsHolder']/node()") or [''])[0],

        'scientificName': doc.xpath("arr[@name='scientificName']/str/node()"),
        'site': doc.xpath("arr[@name='site']/str/node()"),
        'size': (doc.xpath("long[@name='size']/node()") or [''])[0],
        'sku': (doc.xpath("str[@name='sku']/node()") or [''])[0],
        'isDocumentedBy': doc.xpath("arr[@name='isDocumentedBy']/str/node()"),
    }
    return properties

def name_from_email(email):
    email_re = '(.+?)@'
    name = re.search(email_re, email).group(1)
    if '.' in name:
        name = name.replace('.', ' ').title()
    return name

def get_contributors(doc):
    author = (doc.xpath("str[@name='author']/node()") or [NAME])[0]
    submitters = doc.xpath("str[@name='submitter']/node()")
    contributors = doc.xpath("arr[@name='origin']/str/node()")

    unique_contributors = list(set([author] + contributors))

    # this is the index of the author in the unique_contributors list
    if author != '':
        author_index = unique_contributors.index(author)
    else:
        author_index = None

    # grabs the email if there is one, this should go with the author index
    email = ''
    for submitter in submitters:
        if '@' in submitter:
            email = submitter

    contributor_list = []
    for index, contributor in enumerate(unique_contributors):
        if author_index != None and index == author_index:
            name = name_from_email(email)
            name = HumanName(name)
            contributor_dict = {
                'prefix': name.title,
                'given': name.first,
                'middle': name.middle,
                'family': name.last,
                'suffix': name.suffix,
                'email': email,
                'ORCID': ''
            }
            contributor_list.append(contributor_dict)
        else:
            name = HumanName(contributor)
            contributor_list.append({
                'prefix': name.title,
                'given': name.first,
                'middle': name.middle,
                'family': name.last,
                'suffix': name.suffix,
                'email': '',
                'ORCID': ''
            })

    return contributor_list


def get_ids(doc, raw_doc):
    # id
    doi = ''
    service_id = raw_doc.get('docID')
    if 'doi' in service_id:
        # regex for just getting doi out of crazy urls and sometimes not urls
        doi_re = '10\\.\\d{4}/\\w*\\.\\w{5}|10\\.\\d{4}/\\w*/\\w*\\.\\d*.\\d*'
        regexed_doi = re.search(doi_re, service_id).group(0)
        doi = regexed_doi
    url = (doc.xpath('//str[@name="dataUrl"]/node()') or [''])[0]
    ids = {'service_id':service_id, 'doi': doi, 'url':url}

    return ids

def get_tags(doc):
    tags = doc.xpath("//arr[@name='keywords']/str/node()")
    return [tag.lower() for tag in tags]

def get_date_updated(doc):
    pass

def get_date_created(doc):
    date_created = doc.xpath("date[@name='dateUploaded']/node()")[0]
    return parse(date_created).isoformat()

def normalize(raw_doc, timestamp):
    raw_doc_text = raw_doc.get('doc')
    doc = etree.XML(raw_doc_text)

    normalized_dict = {
            'title': (doc.xpath("str[@name='title']/node()") or [''])[0],
            'contributors': get_contributors(doc),
            'properties': get_properties(doc),
            'description': (doc.xpath("str[@name='abstract']/node()") or [''])[0],
            'id': get_ids(doc, raw_doc),
            'tags': get_tags(doc),
            'source': NAME,
            'dateCreated': date_created,
            'dateUpdated': 'du',
            'timestamp': str(timestamp)
    }

    return NormalizedDocument(normalized_dict)


if __name__ == '__main__':
    print(lint(consume, normalize))
