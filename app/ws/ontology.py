# ontology
# Created by JKChang
# 05/07/2018, 15:05
# Tag:
# Description:
import json
import logging
import ssl

from flask import current_app as app
from flask import request, jsonify
from flask_restful import Resource, reqparse
from flask_restful_swagger import swagger
from owlready2 import get_ontology, urllib

from app.ws.isaApiClient import IsaApiClient
from app.ws.mtblsWSclient import WsClient
from app.ws.ontology_info import entity
from app.ws.ontology_info import onto_information

logger = logging.getLogger('wslog')
iac = IsaApiClient()
wsc = WsClient()


# Allow for a more detailed logging when on DEBUG mode
def log_request(request_obj):
    if app.config.get('DEBUG'):
        if app.config.get('DEBUG_LOG_HEADERS'):
            logger.debug('REQUEST HEADERS -> %s', request_obj.headers)
        if app.config.get('DEBUG_LOG_BODY'):
            logger.debug('REQUEST BODY    -> %s', request_obj.data)
        if app.config.get('DEBUG_LOG_JSON'):
            try:
                logger.debug('REQUEST JSON    -> %s', request_obj.json)
            except:
                logger.debug('REQUEST JSON    -> EMPTY')


class Ontology(Resource):

    @swagger.operation(
        summary="Get ontology onto_information",
        notes="Get ontology onto_information.",
        parameters=[
            {
                "name": "term",
                "description": "Ontology term",
                "required": False,
                "allowEmptyValue": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string"
            },

            {
                "name": "branch",
                "description": "starting branch of ontology",
                "required": False,
                "allowEmptyValue": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string",
                "enum": ["factors", "roles", "taxonomy", "characteristics", "publication", "design descriptor", "unit"]
            },

            # {
            #     "name": "mapping",
            #     "description": "starting branch of ontology",
            #     "required": False,
            #     "allowEmptyValue": True,
            #     "allowMultiple": False,
            #     "paramType": "query",
            #     "dataType": "string",
            #     "enum": ["typo", "exact"]
            # }
        ],
        responseMessages=[
            {
                "code": 200,
                "message": "OK."
            },
            {
                "code": 400,
                "message": "Bad Request. Server could not understand the request due to malformed syntax."
            },
            {
                "code": 401,
                "message": "Unauthorized. Access to the resource requires user authentication."
            },
            {
                "code": 403,
                "message": "Forbidden. Access to the study is not allowed for this user."
            },
            {
                "code": 404,
                "message": "Not found. The requested identifier is not valid or does not exist."
            }
        ]
    )
    def get(self):
        log_request(request)
        parser = reqparse.RequestParser()

        parser.add_argument('term', help="Ontology term")
        term = None
        if request.args:
            args = parser.parse_args(req=request)
            term = args['term']

        parser.add_argument('branch', help='Starting branch of ontology')
        branch = None
        if request.args:
            args = parser.parse_args(req=request)
            branch = args['branch']

        # parser.add_argument('mapping', help='Mapping approcaches')
        # mapping = None
        # if request.args:
        #     args = parser.parse_args(req=request)
        #     mapping = args['mapping']

        # Onto loading
        logger.info('Getting Ontology term %s', term)
        onto = get_ontology('./tests/Metabolights.owl').load()
        info = onto_information(onto)

        result = []

        # if only branch, search all branch
        if not term and branch:

            start_cls = onto.search_one(label=branch)
            clses = info.get_subs(start_cls)

            for cls in clses:
                enti = entity(name=cls.label[0], iri=cls.iri, ontoName='MTBLS')
                result.append(enti)

        # if keyword !=  null
        elif term:

            if branch:
                start_cls = onto.search_one(label=branch)
                clses = info.get_subs(start_cls)

                res_cls = []
                # exact match
                if term.lower() in [cls.label[0].lower() for cls in clses]:
                    if onto.search_one(label=term.lower()) is not None:
                        c = onto.search_one(label=term.lower())
                    elif onto.search_one(label=term.title()) is not None:
                        c = onto.search_one(label=term.title())
                    else:
                        c = onto.search_one(label=term.upper())

                    subs = info.get_subs(c)
                    res_cls = [c] + subs

                    for cls in res_cls:
                        enti = entity(name=cls.label[0], iri=cls.iri, obo_ID=cls.name, ontoName='MTBLS')
                        result.append(enti)

                # fuzzy match
                if len(result) == 0:
                    for cls in clses:
                        if term.lower() in cls.label[0].lower():
                            res_cls.append(cls)

                    for cls in res_cls:
                        enti = entity(name=cls.label[0], iri=cls.iri, obo_ID=cls.name, ontoName='MTBLS')
                        result.append(enti)

            # if branch == null, search whole ontology
            if len(result) == 0:
                try:
                    if onto.search_one(label=term.lower()) is not None:
                        c = onto.search_one(label=term.lower())
                    elif onto.search_one(label=term.title()) is not None:
                        c = onto.search_one(label=term.title())
                    else:
                        c = onto.search_one(label=term.upper())
                    enti = entity(name=c.label[0], iri=c.iri, ontoName='MTBLS')
                    result.append(enti)
                except Exception as e:
                    print(e.args)
                    logger.info(e.args)

            # Zooma Search
            if len(result) == 0:
                print("Can't find query in MTBLS ontology, requesting Zooma")
                logger.info("Can't find query in MTBLS ontology, requesting Zooma")
                try:
                    temp = getZoomaTerm(term)
                    for t in temp:
                        if t.Zooma_confidence in ['GOOD', 'HIGH']:
                            result.append(t)
                except Exception as e:
                    print(e.args)
                    logger.info(e.args)

            # OLS Search
            if len(result) == 0:
                print("Can't query it in Zooma, requesting OLS")
                logger.info("Can't query it in Zooma, requesting OLS")
                try:
                    result = getOLSTerm(term)
                except  Exception as e:
                    print(e.args)
                    logger.info(e.args)

            # Bioportal Search
            if len(result) == 0:
                print("Can't query it in OLS, request Bioportal")
                try:
                    result = getBioportalTerm(term)
                except  Exception as e:
                    print(e.args)
                    logger.info(e.args)
                    print("Can't query it in Bioportal")

        else:
            print('Error')

        response = []

        for cls in result:
            temp = '''    {
                    "comments": [],
                    "annotationValue": "investigator",
                    "termSource": {
                        "comments": [],
                        "ontology_name": "",
                        "file": "",
                        "provenance_name":"",
                        "version": "",
                        "description": ""
                    },
                    "termAccession": ""
                }'''

            d = json.loads(str(temp))
            try:
                d['annotationValue'] = str(cls.name)
                d["termAccession"] = str(cls.iri)
                d['termSource']['ontology_name'] = str(cls.ontoName)
                d['termSource']['file'] = str(cls.provenance_uri)
                d['termSource']['provenance_name'] = str(cls.provenance_name)
                d['termSource']['version'] = str(getOnto_version(cls.ontoName))
                d['termSource']['description'] = str(getOnto_title(cls.ontoName))
            except:
                pass

            response.append(d)

        # response = [{'SubClass': x} for x in res]
        return jsonify({"OntologyTerm": response})


def getZoomaTerm(keyword):
    res = []
    try:
        url = 'http://snarf.ebi.ac.uk:8480/spot/zooma/v2/api/services/annotate?propertyValue=' + keyword.replace(' ',"+")
        # url = 'https://www.ebi.ac.uk/spot/zooma/v2/api/services/annotate?propertyValue=' + keyword.replace(' ', "+")
        ssl._create_default_https_context = ssl._create_unverified_context
        fp = urllib.request.urlopen(url)
        content = fp.read().decode('utf8')
        json_str = json.loads(content)
        for term in json_str:
            iri = term['semanticTags'][0]
            if 'mesh' in iri.lower():
                ontoName = 'MESH'
            elif 'nci' in iri.lower():
                ontoName = 'NCIT'
            elif 'bao' in iri.lower():
                ontoName = 'BAO'
            else:
                ontoName = getOnto_Name(iri)

            enti = entity(name=term["annotatedProperty"]['propertyValue'].title(),
                          iri=iri,
                          obo_ID=iri.rsplit('/', 1)[-1],
                          ontoName=ontoName,
                          Zooma_confidence=term['confidence'])

            try:
                provenance_name = term['derivedFrom']['provenance']['source']['name']
                provenance_uri = term['derivedFrom']['provenance']['source']['uri']
            except:
                provenance_name = ''
                provenance_uri = ''

            if 'http' not in provenance_name:
                enti.provenance_name = provenance_name
            else:
                enti.provenance_name = ontoName

            enti.provenance_uri = provenance_uri

            if enti.provenance_name =='metabolights':
                res = [enti] + res
            else:
                res.append(enti)
                
            if len(res) >= 5:
                break
    except Exception as e:
        logger.error('getZooma' + str(e))
    return res


def getOLSTerm(keyword):
    res = []
    a = keyword
    try:
        # https://www.ebi.ac.uk/ols/api/search?q=lung&groupField=true&queryFields=label,synonym&fieldList=iri,label,short_form,obo_id,ontology_name,ontology_prefix
        url = 'https://www.ebi.ac.uk/ols/api/search?q=' + keyword.replace(' ', "+") + \
              '&groupField=true' \
              '&queryFields=label,synonym' \
              '&fieldList=iri,label,short_form,obo_id,ontology_name,ontology_prefix'  # '&exact=true' \
        fp = urllib.request.urlopen(url)
        content = fp.read().decode('utf-8')
        j_content = json.loads(content)
        responses = j_content["response"]['docs']

        for term in responses:
            enti = entity(name=term['label'].title(),
                          iri=term['iri'],
                          obo_ID=term['obo_id'],
                          ontoName=term['ontology_prefix'],
                          provenance_name=term['ontology_prefix'])
            res.append(enti)
            if len(res) >= 5:
                break

    except Exception as e:
        logger.error('getOLS' + str(e))
    return res


def getBioportalTerm(keyword):
    res = []
    try:
        url = 'http://data.bioontology.org/search?q=' + keyword.replace(' ', "+")  # + '&require_exact_match=true'
        request = urllib.request.Request(url)
        request.add_header('Authorization', 'apikey token=c60c5add-63c6-4485-8736-3f495146aee3')
        response = urllib.request.urlopen(request)
        content = response.read().decode('utf-8')
        j_content = json.loads(content)

        iri_record = []

        for term in j_content['collection']:
            iri = term['@id']
            if iri in iri_record:
                continue

            if 'mesh' in iri.lower():
                ontoName = 'MESH'
            elif 'nci' in iri.lower():
                ontoName = 'NCIT'
            elif 'bao' in iri.lower():
                ontoName = 'BAO'
            else:
                ontoName = getOnto_Name(iri)

            enti = entity(name=term['prefLabel'],
                          iri=iri,
                          obo_ID=iri.rsplit('/', 1)[-1],
                          ontoName=ontoName)
            res.append(enti)
            iri_record.append(iri)
            if len(res) >= 5:
                break
    except Exception as e:
        logger.error('getBioportal' + str(e))
    return res


def getOnto_Name(iri):
    # get ontology name by giving iri of entity
    substring = iri.rsplit('/', 1)[-1]
    return ''.join(x for x in substring if x.isalpha())

def getOnto_title(pre_fix):
    url = 'https://www.ebi.ac.uk/ols/api/ontologies/' + pre_fix
    fp = urllib.request.urlopen(url)
    content = fp.read().decode('utf-8')
    j_content = json.loads(content)
    return j_content['config']['title']

def getOnto_version(pre_fix):
    url = 'https://www.ebi.ac.uk/ols/api/ontologies/' + pre_fix
    fp = urllib.request.urlopen(url)
    content = fp.read().decode('utf-8')
    j_content = json.loads(content)
    return j_content['config']['version']
