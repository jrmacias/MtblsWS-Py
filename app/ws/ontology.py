#  EMBL-EBI MetaboLights - https://www.ebi.ac.uk/metabolights
#  Metabolomics team
#
#  European Bioinformatics Institute (EMBL-EBI), European Molecular Biology Laboratory, Wellcome Genome Campus, Hinxton, Cambridge CB10 1SD, United Kingdom
#
#  Last modified: 2019-May-08
#  Modified by:   kenneth
#
#  Copyright 2019 EMBL - European Bioinformatics Institute
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

import datetime
import re

import gspread
import numpy as np
import requests
from flask import jsonify
from flask import request, abort
from flask_restful import Resource, reqparse
from flask_restful_swagger import swagger
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials

from app.ws.isaApiClient import IsaApiClient
from app.ws.mtblsWSclient import WsClient
from app.ws.ontology_info import *
from app.ws.utils import log_request

logger = logging.getLogger('wslog')
iac = IsaApiClient()
wsc = WsClient()


# # Allow for a more detailed logging when on DEBUG mode
# def log_request(request_obj):
#     if app.config.get('DEBUG'):
#         if app.config.get('DEBUG_LOG_HEADERS'):
#             logger.debug('REQUEST HEADERS -> %s', request_obj.headers)
#         if app.config.get('DEBUG_LOG_BODY'):
#             logger.debug('REQUEST BODY    -> %s', request_obj.data)
#         if app.config.get('DEBUG_LOG_JSON'):
#             try:
#                 logger.debug('REQUEST JSON    -> %s', request_obj.json)
#             except:
#                 logger.debug('REQUEST JSON    -> EMPTY')


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
                "enum": ["factor", "role", "taxonomy", "characteristic", "publication", "design descriptor", "unit",
                         "column type", "instruments", "confidence", "sample type"]
            },

            {
                "name": "mapping",
                "description": "taxonomy search approach",
                "required": False,
                "allowEmptyValue": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string",
                "enum": ["typo", "exact", "fuzzy"]
            },

            {
                "name": "queryFields",
                "description": "Specifcy the fields to return, the default is all options: {MTBLS,MTBLS_Zooma,Zooma,"
                               "OLS, Bioportal}",
                "required": False,
                "allowEmptyValue": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string",
            },

            {
                "name": "ontology",
                "description": "Restrict a search to a set of ontologies",
                "required": False,
                "allowEmptyValue": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string",
            }

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
            if term:
                term = term.strip()

        parser.add_argument('branch', help='Starting branch of ontology')
        branch = None
        if request.args:
            args = parser.parse_args(req=request)
            branch = args['branch']
            if branch:
                branch = branch.strip()

        parser.add_argument('mapping', help='Mapping approaches')
        mapping = None
        if request.args:
            args = parser.parse_args(req=request)
            mapping = args['mapping']

        parser.add_argument('queryFields', help='query Fields')
        queryFields = None  # ['MTBLS', 'MTBLS_Zooma', 'Zooma','OLS', 'Bioportal']
        if request.args:
            args = parser.parse_args(req=request)
            queryFields = args['queryFields']
            if queryFields:
                try:
                    reg = '\{([^}]+)\}'
                    queryFields = re.findall(reg, queryFields)[0].split(',')
                except:
                    try:
                        queryFields = queryFields.split(',')
                    except Exception as e:
                        print(e.args)

        parser.add_argument('ontology', help='ontology')
        ontology = None
        if request.args:
            args = parser.parse_args(req=request)
            ontology = args['ontology']
            if ontology:
                try:
                    reg = '\{([^}]+)\}'
                    ontology = re.findall(reg, ontology)[0].split(',')
                except:
                    try:
                        ontology = ontology.split(',')
                    except Exception as e:
                        print(e.args)

        if ontology != None:
            ontology = [x.lower() for x in ontology]

        result = []

        if term in [None, ''] and branch is None:
            return []

        if ontology not in [None, '']:  # if has ontology searching restriction
            logger.info('Search %s in' % ','.join(ontology))
            print('Search %s in' % ','.join(ontology))
            try:
                result = getOLSTerm(term, mapping, ontology=ontology)
            except Exception as e:
                print(e.args)
                logger.info(e.args)

        else:
            if queryFields in [None, '']:  # if found the term, STOP
                logger.info('Search %s from resources one by one' % term)
                print('Search %s from resources one by one' % term)
                result = getMetaboTerm(term, branch, mapping)

                if len(result) == 0:
                    print("Can't find query in MTBLS ontology, search metabolights-zooma.tsv")
                    logger.info("Can't find query in MTBLS ontology, search metabolights-zooma.tsv")
                    try:
                        result = getMetaboZoomaTerm(term, mapping)
                    except Exception as e:
                        print(e.args)
                        logger.info(e.args)

                if len(result) == 0:
                    print("Can't query it in Zooma.tsv, requesting OLS")
                    logger.info("Can't query it in Zooma.tsv, requesting OLS")
                    try:
                        result = getOLSTerm(term, mapping, ontology=ontology)
                    except Exception as e:
                        print(e.args)
                        logger.info(e.args)

                if len(result) == 0:
                    print("Can't find query in OLS, requesting Zooma")
                    logger.info("Can't find query in OLS, requesting Zooma")
                    try:
                        result = getZoomaTerm(term)
                    except Exception as e:
                        print(e.args)
                        logger.info(e.args)

                if len(result) == 0:
                    print("Can't query it in Zooma, request Bioportal")
                    logger.info("Can't query it in Zooma, request Bioportal")
                    try:
                        result = getBioportalTerm(term)
                    except Exception as e:
                        print(e.args)
                        logger.info(e.args)

            else:
                if 'MTBLS' in queryFields:
                    result += getMetaboTerm(term, branch, mapping)

                if 'MTBLS_Zooma' in queryFields:
                    result += getMetaboZoomaTerm(term, mapping)

                if 'OLS' in queryFields:
                    result += getOLSTerm(term, mapping)

                if 'Zooma' in queryFields:
                    result += getZoomaTerm(term, mapping)

                if 'Bioportal' in queryFields:
                    result += getBioportalTerm(term)

        response = []

        result = removeDuplicated(result)

        # add WoRMs terms as a entity
        if branch == 'taxonomy':
            r = getWormsTerm(term)
            result += r
        else:
            pass

        if term not in [None, '']:
            exact = [x for x in result if x.name.lower() == term.lower()]
            rest = [x for x in result if x not in exact]

            # "factor", "role", "taxonomy", "characteristic", "publication", "design descriptor", "unit",
            #                          "column type", "instruments", "confidence", "sample type"

            if branch == 'taxonomy':
                priority = {'MTBLS': 0, 'NCBITAXON': 1, 'WoRMs': 2, 'EFO': 3, 'BTO': 4, 'CHEBI': 5, 'CHMO': 6,
                            'NCIT': 6,
                            'PO': 8}

            if branch == 'factor':
                priority = {'MTBLS': 0, 'EFO': 1, 'MESH': 2, 'BTO': 3, 'CHEBI': 4, 'CHMO': 5, 'NCIT': 6, 'PO': 7}

            if branch == 'design descriptor':
                priority = {'MTBLS': 0, 'EFO': 1, 'MESH': 2, 'BTO': 3, 'CHEBI': 4, 'CHMO': 5, 'NCIT': 6, 'PO': 7}

            else:
                priority = {'MTBLS': 0, 'EFO': 1, 'NCBITAXON': 2, 'BTO': 3, 'CHEBI': 4, 'CHMO': 5, 'NCIT': 6, 'PO': 7}

            exact = setPriority(exact, priority)
            rest = reorder(rest, term)
            result = exact + rest

        # result = removeDuplicated(result)

        for cls in result:
            temp = '''    {
                            "comments": [],
                            "annotationValue": "",
                            "annotationDefinition": "", 
                            "termAccession": "",
                            "wormsID": "", 
                            
                            "termSource": {
                                "comments": [],
                                "name": "",
                                "file": "",
                                "provenanceName": "",
                                "version": "",
                                "description": ""
                            }                            
                        }'''

            d = json.loads(str(temp))
            try:
                d['annotationValue'] = cls.name
                d["annotationDefinition"] = cls.definition
                if branch == 'taxonomy':
                    d['wormsID'] = cls.iri.rsplit('id=', 1)[-1]
                d["termAccession"] = cls.iri
                d['termSource']['name'] = cls.ontoName
                d['termSource']['provenanceName'] = cls.provenance_name

                if cls.ontoName == 'MTBLS':
                    d['termSource']['file'] = 'https://www.ebi.ac.uk/metabolights/'
                    d['termSource']['provenanceName'] = 'Metabolights'
                    d['termSource']['version'] = '1.0'
                    d['termSource']['description'] = 'Metabolights Ontology'
            except Exception as e:
                pass

            if cls.provenance_name == 'metabolights-zooma':
                d['termSource']['version'] = str(datetime.datetime.now().date())
            response.append(d)

        # response = [{'SubClass': x} for x in res]
        print('--' * 30)
        return jsonify({"OntologyTerm": response})

    # =========================== put =============================================

    @swagger.operation(
        summary="Add new entity to metabolights ontology",
        notes='''Add new entity to metabolights ontology.
              <br>
              <pre><code>
{
  "ontologyEntity": {
    "termName": "ABCC5",
    "definition": "The protein-coding gene ABCC5 located on the chromosome 3 mapped at 3q27.",
    "superclass": "design descriptor"
  }
}</code></pre>''',

        parameters=[
            {
                "name": "user_token",
                "description": "User API token",
                "paramType": "header",
                "type": "string",
                "required": True,
                "allowMultiple": False
            },
            {
                "name": "protocol",
                "description": 'Ontology Entity in JSON format.',
                "paramType": "body",
                "type": "string",
                "format": "application/json",
                "required": True,
                "allowMultiple": False
            }
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
    def put(self):
        log_request(request)
        parser = reqparse.RequestParser()

        # User authentication
        user_token = None
        if "user_token" in request.headers:
            user_token = request.headers["user_token"]
        else:
            abort(401)

        # check for access rights
        is_curator, read_access, write_access, obfuscation_code, study_location, release_date, submission_date, study_status = \
            wsc.get_permissions('MTBLS1', user_token)
        if not write_access:
            abort(403)

        data_dict = None
        try:
            data_dict = json.loads(request.data.decode('utf-8'))['ontologyEntity']
        except Exception as e:
            logger.info(e)
            abort(400)

        logger.info('Add %s to Metabolights ontology' % data_dict['termName'])
        print('Add %s to Metabolights ontology' % data_dict['termName'])

        description = None
        if len(data_dict['definition']) > 0:
            description = data_dict['definition']
        try:
            addEntity(new_term=data_dict['termName'], supclass=data_dict['superclass'], definition=description)
        except Exception as e:
            logger.info(e)
            abort(400)


class Placeholder(Resource):
    @swagger.operation(
        summary="Get placeholder terms from study files",
        notes="Get placeholder terms",
        parameters=[
            {
                "name": "query",
                "description": "Data field to extract from study",
                "required": True,
                "allowEmptyValue": False,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string",
                "enum": ["factor", "design descriptor", "organism"]
            },
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
                "code": 404,
                "message": "Not found. The requested identifier is not valid or does not exist."
            }
        ]
    )
    def get(self):
        log_request(request)
        parser = reqparse.RequestParser()

        query = ''
        parser.add_argument('query', help='data field to extract from studies')
        if request.args:
            args = parser.parse_args(req=request)
            query = args['query']
            if query is None:
                abort(400)
            if query:
                query = query.strip().lower()

        url = app.config.get('GOOGLE_SHEET_URL')
        sheet_name = ''
        col = []

        if query == 'factor':
            sheet_name = 'factor'

            col = ['operation(Update/Add/Delete/Zooma/MTBLS)', 'status (Done/Error)', 'studyID', 'old_name', 'name',
                   'annotationValue', 'termAccession', 'superclass', 'definition']

        elif query == 'design descriptor':
            sheet_name = 'design descriptor'

            col = ['operation(Update/Add/Delete/Zooma/MTBLS)', 'status (Done/Error)', 'studyID', 'old_name', 'name',
                   'matched_iri', 'superclass', 'definition']
        elif query == 'organism':
            sheet_name = 'organism'

            col = ['operation(Update/Add/Delete/Zooma/MTBLS)', 'status (Done/Error)', 'studyID', 'old_organism',
                   'organism', 'organism_ref', 'organism_url', 'old_organismPart', 'organismPart', 'organismPart_ref',
                   'organismPart_url', 'superclass', 'definition']
        else:
            abort(400)

        try:
            google_df = getGoogleSheet(url, sheet_name)

        except Exception as e:
            google_df = pd.DataFrame(columns=col)
            print(e.args)
            logger.info('Fail to load spreadsheet from Google')
            logger.info(e.args)

        df = pd.DataFrame(get_metainfo(query))
        df_connect = pd.concat([google_df, df], ignore_index=True, sort=False)
        if query in ['factor', 'design descriptor']:
            df_connect = df_connect.reindex(columns=col) \
                .replace(np.nan, '', regex=True) \
                .drop_duplicates(keep='first', subset=["studyID", "old_name"])

        if query == 'organism':
            df_connect = df_connect.replace('', np.nan, regex=True)
            df_connect = df_connect.dropna(subset=['old_organism', 'old_organismPart'], thresh=1)
            df_connect = df_connect.reindex(columns=col) \
                .replace(np.nan, '', regex=True) \
                .drop_duplicates(keep='first', subset=["studyID", "old_organism", "old_organismPart"])

        adding_count = df_connect.shape[0] - google_df.shape[0]

        # Ranking the row according to studyIDs
        def extractNum(s):
            num = re.findall("\d+", s)[0]
            return int(num)

        df_connect['num'] = df_connect['studyID'].apply(extractNum)
        df_connect = df_connect.sort_values(by=['num'])
        df_connect = df_connect.drop('num', axis=1)

        replaceGoogleSheet(df_connect, url, sheet_name)
        return jsonify({'success': True, 'add': adding_count})

    # ============================ Placeholder put ===============================
    @swagger.operation(
        summary="Make changes according to google old_term sheets",
        notes="Update/add/Delete placeholder terms",
        parameters=[
            {
                "name": "query",
                "description": "Data field to change",
                "required": True,
                "allowEmptyValue": False,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string",
                "enum": ["factor", "design descriptor", "organism"]
            },
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
                "code": 404,
                "message": "Not found. The requested identifier is not valid or does not exist."
            }
        ]
    )
    def put(self):
        log_request(request)
        parser = reqparse.RequestParser()

        query = ''
        parser.add_argument('query', help='data field to update')
        if request.args:
            args = parser.parse_args(req=request)
            query = args['query']
            if query is None:
                abort(400)
            if query:
                query = query.strip().lower()

        google_url = app.config.get('GOOGLE_SHEET_URL')
        sheet_name = ''

        # get sheet_name
        if query == 'factor':
            sheet_name = 'factor'
            # col = ['operation(Update/Add/Delete/Zooma/MTBLS)', 'status (Done/Error)', 'studyID', 'old_name', 'name',
            #        'annotationValue', 'termAccession', 'superclass', 'definition']

        elif query == 'design descriptor':
            sheet_name = 'design descriptor'
            # col = ['operation(Update/Add/Delete/Zooma/MTBLS)', 'status (Done/Error)', 'studyID', 'old_name', 'name',
            #        'matched_iri', 'superclass', 'definition']

        elif query == 'organism':
            sheet_name = 'organism'
            # col = ['operation(Update/Add/Delete/Zooma/MTBLS)', 'status (Done/Error)', 'studyID', 'old_organism',
            #        'organism', 'organism_ref', 'organism_url', 'old_organismPart', 'organismPart', 'organismPart_ref',
            #        'organismPart_url', 'superclass', 'definition']

        else:
            abort(400)

        # Load google sheet
        google_df = getGoogleSheet(google_url, sheet_name)

        ch = google_df[
            (google_df['operation(Update/Add/Delete/Zooma/MTBLS)'] != '') & (google_df['status (Done/Error)'] == '')]

        for index, row in ch.iterrows():
            if query == 'factor':
                operation, studyID, old_term, term, annotationValue, termAccession, superclass, definition = \
                    row['operation(Update/Add/Delete/Zooma/MTBLS)'], row['studyID'], row['old_name'], row['name'], row[
                        'annotationValue'], row['termAccession'], row['superclass'], row['definition']

                source = '/metabolights/ws/studies/{study_id}/factors'.format(study_id=studyID)
                ws_url = app.config.get('MTBLS_WS_HOST') + ':' + str(app.config.get('PORT')) + source

                if operation.lower() in ['update', 'u', 'add', 'A']:
                    # ws_url = 'https://www.ebi.ac.uk/metabolights/ws/studies/{study_id}/factors'.format(study_id=studyID)
                    protocol = '''
                                                {
                                                    "factorName": "",
                                                    "factorType": {
                                                      "annotationValue": "",
                                                      "termSource": {
                                                        "name": "",
                                                        "file": "",
                                                        "version": "",
                                                        "description": ""
                                                      },
                                                      "termAccession": ""
                                                    }                       
                                                }
                                                '''
                    try:
                        onto_name = getOnto_Name(termAccession)[0]
                        onto_iri, onto_version, onto_description = getOnto_info(onto_name)

                        temp = json.loads(protocol)
                        temp["factorName"] = term
                        temp["factorType"]["annotationValue"] = annotationValue
                        temp["factorType"]['termSource']['name'] = onto_name
                        temp["factorType"]['termSource']['file'] = onto_iri
                        temp["factorType"]['termSource']['version'] = onto_version
                        temp["factorType"]['termSource']['description'] = onto_description
                        temp["factorType"]['termAccession'] = termAccession

                        data = json.dumps({"factor": temp})

                        if operation.lower() in ['update', 'u']:  # Update factor
                            response = requests.put(ws_url, params={'name': old_term},
                                                    headers={'user_token': app.config.get('METABOLIGHTS_TOKEN'),
                                                             'save_audit_copy': 'true'}, data=data)
                            print('Made correction from {old_term} to {matchterm}({matchiri}) in {studyID}'.format(
                                old_term=old_term, matchterm=annotationValue, matchiri=termAccession, studyID=studyID))

                        else:  # Add factor
                            response = requests.post(ws_url,
                                                     headers={'user_token': app.config.get('METABOLIGHTS_TOKEN'),
                                                              'save_audit_copy': 'true'}, data=data)

                            print('Add {old_term} ({matchiri}) in {studyID}'.format(old_term=old_term,
                                                                                    matchiri=termAccession,
                                                                                    studyID=studyID))
                        if response.status_code == 200:
                            google_df.loc[index, 'status (Done/Error)'] = 'Done'
                        else:
                            google_df.loc[index, 'status (Done/Error)'] = 'Error'

                        replaceGoogleSheet(google_df, google_url, sheet_name)
                    except Exception as e:
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                # Delete factor
                elif operation.lower() in ['delete', 'D']:
                    try:
                        response = requests.delete(ws_url, params={'name': old_term},
                                                   headers={'user_token': app.config.get('METABOLIGHTS_TOKEN'),
                                                            'save_audit_copy': 'true'})

                        print('delete {old_term} from {studyID}'.format(old_term=old_term, studyID=studyID))

                        if response.status_code == 200:
                            google_df.loc[index, 'status (Done/Error)'] = 'Done'
                        else:
                            google_df.loc[index, 'status (Done/Error)'] = 'Error'

                        replaceGoogleSheet(google_df, google_url, sheet_name)

                    except Exception as e:
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                # add factor term to MTBLS ontology
                elif operation.lower() == 'mtbls':
                    try:
                        row['status (Done/Error)'] = 'Done'
                        source = '/metabolights/ws/ebi-internal/ontology'

                        protocol = '''
                                     {
                                      "ontologyEntity": {
                                        "termName": " ",
                                        "definition": " ",
                                        "superclass": " "
                                      }
                                    }
                                   '''

                        temp = json.loads(protocol)
                        temp["ontologyEntity"]["termName"] = annotationValue
                        temp["ontologyEntity"]["definition"] = definition
                        temp["ontologyEntity"]["superclass"] = superclass

                        data = json.dumps({"ontologyEntity": temp})
                        response = requests.put(ws_url, headers={'user_token': app.config.get('METABOLIGHTS_TOKEN')},
                                                protocol=data)
                        print('add term {newterm} to {superclass} branch'.format(newterm=annotationValue,
                                                                                 superclass=superclass))

                        if response.status_code == 200:
                            google_df.loc[index, 'status (Done/Error)'] = 'Done'
                        else:
                            google_df.loc[index, 'status (Done/Error)'] = 'Error'

                        replaceGoogleSheet(google_df, google_url, sheet_name)

                    except Exception as e:
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                # add factor term to zooma
                elif operation.lower() == 'zooma':
                    try:
                        addZoomaTerm(studyID, term, annotationValue, termAccession)
                        result = 'Done'
                    except Exception as e:
                        result = 'Error'
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                    google_df.loc[index, 'status (Done/Error)'] = result
                    replaceGoogleSheet(google_df, google_url, sheet_name)

                else:
                    logger.info('Wrong operation tag in the spreadsheet')
                    abort(400)


            elif query == 'design descriptor':

                operation, studyID, old_term, term, matched_iri, superclass, \
                definition = row['operation(Update/Add/Delete/Zooma/MTBLS)'], row['studyID'], row['old_name'], row[
                    'name'], row['matched_iri'], row['superclass'], row['definition']

                source = '/metabolights/ws/studies/{study_id}/descriptors'.format(study_id=studyID)
                ws_url = app.config.get('MTBLS_WS_HOST') + ':' + str(app.config.get('PORT')) + source

                # add / update descriptor
                if operation.lower() in ['update', 'U', 'add', 'A']:
                    protocol = '''
                                    {
                                        "annotationValue": " ",
                                        "termSource": {
                                            "name": " ",
                                            "file": " ",
                                            "version": " ",
                                            "description": " "
                                        },
                                        "termAccession": " "
                                    }
                              '''
                    try:
                        onto_name = getOnto_Name(matched_iri)[0]
                        onto_iri, onto_version, onto_description = getOnto_info(onto_name)

                        temp = json.loads(protocol)
                        temp["annotationValue"] = term
                        temp["termSource"]["name"] = onto_name
                        temp["termSource"]["file"] = onto_iri
                        temp["termSource"]["version"] = onto_version
                        temp["termSource"]["description"] = onto_description
                        temp["termAccession"] = matched_iri

                        data = json.dumps({"studyDesignDescriptor": temp})

                        if operation.lower() in ['update', 'U']:  # Update descriptor
                            response = requests.put(ws_url, params={'term': old_term},
                                                    headers={'user_token': app.config.get('METABOLIGHTS_TOKEN'),
                                                             'save_audit_copy': 'true'},
                                                    data=data)
                            print('Made correction from {old_term} to {matchterm}({matchiri}) in {studyID}'.
                                  format(old_term=old_term, matchterm=old_term, matchiri=matched_iri, studyID=studyID))
                        else:  # Add descriptor
                            response = requests.post(ws_url,
                                                     headers={'user_token': app.config.get('METABOLIGHTS_TOKEN'),
                                                              'save_audit_copy': 'true'},
                                                     data=data)
                            print('Add {old_term} to ({matchiri}) in {studyID}'.
                                  format(old_term=old_term, matchiri=matched_iri, studyID=studyID))

                        if response.status_code == 200:
                            google_df.loc[index, 'status (Done/Error)'] = 'Done'
                        else:
                            google_df.loc[index, 'status (Done/Error)'] = 'Error'

                        replaceGoogleSheet(google_df, google_url, sheet_name)

                    except Exception as e:
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                # Delete descriptor
                elif operation.lower() in ['delete', 'D']:
                    try:
                        response = requests.delete(ws_url, params={'term': old_term},
                                                   headers={'user_token': app.config.get('METABOLIGHTS_TOKEN'),
                                                            'save_audit_copy': 'true'})
                        print('delete {old_term} from in {studyID}'.format(old_term=old_term, studyID=studyID))

                        if response.status_code == 200:
                            google_df.loc[index, 'status (Done/Error)'] = 'Done'
                        else:
                            google_df.loc[index, 'status (Done/Error)'] = 'Error'

                        replaceGoogleSheet(google_df, google_url, sheet_name)

                    except Exception as e:
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                # add descriptor to MTBLS ontology
                elif operation.lower() == 'mtbls':
                    try:
                        row['status (Done/Error)'] = 'Done'
                        source = '/metabolights/ws/ebi-internal/ontology'

                        protocol = '''
                                     {
                                      "ontologyEntity": {
                                        "termName": " ",
                                        "definition": " ",
                                        "superclass": " "
                                      }
                                    }
                                   '''

                        temp = json.loads(protocol)
                        temp["ontologyEntity"]["termName"] = term
                        temp["ontologyEntity"]["definition"] = definition
                        temp["ontologyEntity"]["superclass"] = superclass

                        data = json.dumps({"ontologyEntity": temp})
                        response = requests.put(ws_url, headers={'user_token': app.config.get('METABOLIGHTS_TOKEN')},
                                                protocol=data)
                        print('add term {newterm} to {superclass} branch'.format(newterm=term,
                                                                                 superclass=superclass))

                        if response.status_code == 200:
                            google_df.loc[index, 'status (Done/Error)'] = 'Done'
                        else:
                            google_df.loc[index, 'status (Done/Error)'] = 'Error'

                        replaceGoogleSheet(google_df, google_url, sheet_name)

                    except Exception as e:
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                # add descriptor term to zooma
                elif operation.lower() == 'zooma':
                    try:
                        addZoomaTerm(studyID, term, term, matched_iri)
                        result = 'Done'
                    except Exception as e:
                        result = 'Error'
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                    google_df.loc[index, 'status (Done/Error)'] = result
                    replaceGoogleSheet(google_df, google_url, sheet_name)

                else:
                    logger.info('Wrong operation tag in the spreadsheet')
                    abort(400)

            # -------------------------------------------------------
            # -------------------------------------------------------
            # -------------------------------------------------------

            elif query == 'organism':

                operation, studyID = row['operation(Update/Add/Delete/Zooma/MTBLS)'], row['studyID']
                old_organism, organism, organism_ref, organism_url \
                    = row['old_organism'], row['organism'], row['organism_ref'], row['organism_url']
                old_organismPart, organismPart, organismPart_ref, organismPart_url \
                    = row['old_organismPart'], row['organismPart'], row['organismPart_ref'], row['organismPart_url']
                superclass, definition = row['superclass'], row['definition']

                source = '/metabolights/ws/studies/{study_id}/organisms'.format(study_id=studyID)
                ws_url = app.config.get('MTBLS_WS_HOST') + ':' + str(app.config.get('PORT')) + source

                # add / update descriptor
                if operation.lower() in ['update', 'U', 'add', 'A']:

                    list_changes = []

                    if organism not in ['', None]:
                        list_changes.append({'old_term': old_organism, 'new_term': organism, 'onto_name': organism_ref,
                                             'term_url': organism_url, 'characteristicsName': 'Organism'})
                    if organismPart not in ['', None]:
                        list_changes.append({'old_term': old_organismPart, 'new_term': organismPart,
                                             'onto_name': organismPart_ref, 'term_url': organismPart_url,
                                             'characteristicsName': 'Organism part'})

                    for change in list_changes:
                        protocol = '''
                                    {
                                            "characteristics": [
                                                {
                                                    "comments": [],
                                                    "characteristicsName": "",
                                                    "characteristicsType": {
                                                        "comments": [],
                                                        "annotationValue": " ",
                                                        "termSource": {
                                                            "comments": [],
                                                            "name": " ",
                                                            "file": " ",
                                                            "version": " ",
                                                            "description": " "
                                                        },
                                                        "termAccession": " "
                                                    }
                                                }
                                            ]
                                        }
                                '''
                        try:
                            if change['onto_name'] in ['', None]:
                                onto_name = getOnto_Name(change['term_url'])[0]
                            else:
                                onto_name = change['onto_name']

                            try:
                                onto_iri, onto_version, onto_description = getOnto_info(change['onto_name'])
                            except Exception as e:
                                logger.info(e)
                                print('Fail to load information about ontology {onto_name}'.format(
                                    onto_name=change['onto_name']))
                                onto_iri, onto_version, onto_description = '', '', ''

                            temp = json.loads(protocol)
                            temp['characteristicsName'] = change['characteristicsName']
                            temp['characteristicsType']['annotationValue'] = change['new_term']
                            temp['characteristicsType']['termSource']['name'] = onto_name
                            temp['characteristicsType']['termSource']['file'] = onto_iri
                            temp['characteristicsType']['termSource']['version'] = onto_version
                            temp['characteristicsType']['termSource']['description'] = onto_description

                            data = json.dumps({"characteristics": temp})

                            if operation.lower() in ['update', 'U']:  # Update descriptor
                                response = requests.put(ws_url, params={'term': change['old_term']},
                                                        headers={'user_token': app.config.get('METABOLIGHTS_TOKEN'),
                                                                 'save_audit_copy': 'true'},
                                                        data=data)
                                print('Made correction from {old_term} to {matchterm}({matchiri}) in {studyID}'.
                                      format(old_term=change['old_term'], matchterm=change['new_term'],
                                             matchiri=change['term_url'], studyID=studyID))
                            else:  # Add characteristic
                                response = requests.post(ws_url,headers={'user_token': app.config.get('METABOLIGHTS_TOKEN')},
                                                         data=data)
                                print('Add {old_term} to ({matchiri}) in {studyID}'.
                                      format(old_term=old_term, matchiri=matched_iri, studyID=studyID))

                            if response.status_code == 200:
                                google_df.loc[index, 'status (Done/Error)'] = 'Done'
                            else:
                                google_df.loc[index, 'status (Done/Error)'] = 'Error'

                            replaceGoogleSheet(google_df, google_url, sheet_name)

                        except Exception as e:
                            google_df.loc[index, 'status (Done/Error)'] = 'Error'
                            logger.info(e)

                # Delete descriptor
                elif operation.lower() in ['delete', 'D']:
                    try:
                        response = requests.delete(ws_url, params={'term': old_term},
                                                   headers={'user_token': app.config.get('METABOLIGHTS_TOKEN'),
                                                            'save_audit_copy': 'true'})
                        print('delete {old_term} from in {studyID}'.format(old_term=old_term, studyID=studyID))

                        if response.status_code == 200:
                            google_df.loc[index, 'status (Done/Error)'] = 'Done'
                        else:
                            google_df.loc[index, 'status (Done/Error)'] = 'Error'

                        replaceGoogleSheet(google_df, google_url, sheet_name)

                    except Exception as e:
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                # add descriptor to MTBLS ontology
                elif operation.lower() == 'mtbls':
                    try:
                        row['status (Done/Error)'] = 'Done'
                        source = '/metabolights/ws/ebi-internal/ontology'

                        protocol = '''
                                      {
                                       "ontologyEntity": {
                                         "termName": " ",
                                         "definition": " ",
                                         "superclass": " "
                                       }
                                     }
                                    '''

                        temp = json.loads(protocol)
                        temp["ontologyEntity"]["termName"] = term
                        temp["ontologyEntity"]["definition"] = definition
                        temp["ontologyEntity"]["superclass"] = superclass

                        data = json.dumps({"ontologyEntity": temp})
                        response = requests.put(ws_url, headers={'user_token': app.config.get('METABOLIGHTS_TOKEN')},
                                                protocol=data)
                        print('add term {newterm} to {superclass} branch'.format(newterm=term,
                                                                                 superclass=superclass))

                        if response.status_code == 200:
                            google_df.loc[index, 'status (Done/Error)'] = 'Done'
                        else:
                            google_df.loc[index, 'status (Done/Error)'] = 'Error'

                        replaceGoogleSheet(google_df, google_url, sheet_name)

                    except Exception as e:
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                # add descriptor term to zooma
                elif operation.lower() == 'zooma':
                    try:
                        addZoomaTerm(studyID, term, term, matched_iri)
                        result = 'Done'
                    except Exception as e:
                        result = 'Error'
                        google_df.loc[index, 'status (Done/Error)'] = 'Error'
                        logger.info(e)

                    google_df.loc[index, 'status (Done/Error)'] = result
                    replaceGoogleSheet(google_df, google_url, sheet_name)

                else:
                    logger.info('Wrong operation tag in the spreadsheet')
                    abort(400)
            # -------------------------------------------------------
            # -------------------------------------------------------
            # -------------------------------------------------------

            else:
                logger.info('Wrong query field requested')
                abort(404)


def get_metainfo(query):
    '''
    get placeholder/wrong-match terms from study investigation file
    :param query: factor / descriptor ...
    :return: list of dictionary results
    '''
    res = []

    def getStudyIDs():
        def atoi(text):
            return int(text) if text.isdigit() else text

        def natural_keys(text):
            return [atoi(c) for c in re.split('(\d+)', text)]

        url = 'https://www.ebi.ac.uk/metabolights/webservice/study/list'
        resp = requests.get(url, headers={'user_token': app.config.get('METABOLIGHTS_TOKEN')})
        studyIDs = resp.json()['content']
        studyIDs.sort(key=natural_keys)
        return studyIDs

    logger.info('Getting {query} terms'.format(query=query))
    studyIDs = getStudyIDs()

    for studyID in studyIDs:
        print(f'get {query} from {studyID}.')
        if query.lower() == "factor":
            url = 'https://www.ebi.ac.uk/metabolights/ws/studies/{study_id}/factors'.format(study_id=studyID)

            try:
                resp = requests.get(url, headers={'user_token': app.config.get('METABOLIGHTS_TOKEN')})
                data = resp.json()

                for factor in data["factors"]:
                    temp_dict = {'studyID': studyID,
                                 'old_name': factor['factorName'],
                                 'annotationValue': factor['factorType']['annotationValue'],
                                 'termAccession': factor['factorType']['termAccession']}

                    if ('placeholder' in factor['factorType']['termAccession']) or (
                            factor['factorName'].lower() != factor['factorType']['annotationValue'].lower()):
                        res.append(temp_dict)
                    else:
                        abort(400)
            except:
                pass

        elif query.lower() == "design descriptor":
            url = 'https://www.ebi.ac.uk/metabolights/ws/studies/{study_id}/descriptors'.format(study_id=studyID)

            try:
                resp = requests.get(url, headers={'user_token': app.config.get('METABOLIGHTS_TOKEN')})
                data = resp.json()

                for descriptor in data['studyDesignDescriptors']:

                    temp_dict = {'studyID': studyID,
                                 'old_name': descriptor['annotationValue'],
                                 'matched_iri': descriptor['termAccession']}

                    if ('placeholder' in temp_dict['matched_iri']) or (len(temp_dict['matched_iri']) == 0):
                        res.append(temp_dict)
                    else:
                        abort(400)
            except:
                pass

        elif query.lower() == "organism":
            url = 'https://www.ebi.ac.uk/metabolights/ws/studies/{study_id}/organisms'.format(study_id=studyID)

            try:
                resp = requests.get(url, headers={'user_token': app.config.get('METABOLIGHTS_TOKEN')})
                data = resp.json()
                for organism in data['organisms']:
                    temp_dict = {'studyID': studyID,
                                 'old_organism': organism['Characteristics[Organism]'],
                                 'organism_ref': organism["Term Source REF"],
                                 'organism_url': organism["Term Accession Number"],
                                 'old_organismPart': organism['Characteristics[Organism part]'],
                                 'organismPart_ref': organism["Term Source REF.1"],
                                 'organismPart_url': organism["Term Accession Number.1"]
                                 }

                    # res.append(temp_dict)

                    if ('placeholder' in temp_dict['organism_url']) or ('placeholder' in temp_dict['organismPart_url']) \
                            or (len(temp_dict['organism_url']) == 0) or (len(temp_dict['organismPart_url']) == 0):
                        res.append(temp_dict)

                    else:
                        abort(400)
            except:
                pass
        else:
            abort(400)
    return res


def insertGoogleSheet(data, url, worksheetName):
    '''
    :param data: list of data
    :param url: url of google sheet
    :param worksheetName: worksheet name
    :return: Nan
    '''
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(app.config.get('GOOGLE_TOKEN'), scope)
    gc = gspread.authorize(credentials)
    try:
        wks = gc.open_by_url(url).worksheet(worksheetName)
        wks.append_row(data, value_input_option='RAW')
    except Exception as e:
        print(e.args)
        logger.info(e.args)


def setGoogleSheet(df, url, worksheetName):
    '''
    set whole dataframe to google sheet, if sheet existed create a new one
    :param df: dataframe want to save to google sheet
    :param url: url of google sheet
    :param worksheetName: worksheet name
    :return: Nan
    '''
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(app.config.get('GOOGLE_TOKEN'), scope)
    gc = gspread.authorize(credentials)
    try:
        wks = gc.open_by_url(url).worksheet(worksheetName)
        print(worksheetName + ' existed... create a new one')
        wks = gc.open_by_url(url).add_worksheet(title=worksheetName + '_1', rows=df.shape[0], cols=df.shape[1])
    except Exception as e:
        wks = gc.open_by_url(url).add_worksheet(title=worksheetName, rows=df.shape[0], cols=df.shape[1])
        logger.info(e.args)
    set_with_dataframe(wks, df)


def getGoogleSheet(url, worksheetName):
    '''
    get google sheet
    :param url: url of google sheet
    :param worksheetName: work sheet name
    :return: data frame
    '''
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(app.config.get('GOOGLE_TOKEN'), scope)
        gc = gspread.authorize(credentials)
        wks = gc.open_by_url(url).worksheet(worksheetName)
        content = wks.get_all_records()
        df = pd.DataFrame(content)
        return df
    except Exception as e:
        logger.info(e.args)


def replaceGoogleSheet(df, url, worksheetName):
    '''
    replace the old google sheet with new data frame, old sheet will be clear
    :param df: dataframe
    :param url: url of google sheet
    :param worksheetName: work sheet name
    :return: Nan
    '''
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(app.config.get('GOOGLE_TOKEN'), scope)
        gc = gspread.authorize(credentials)
        wks = gc.open_by_url(url).worksheet(worksheetName)
        wks.clear()
        set_with_dataframe(wks, df)
    except Exception as e:
        logger.info(e.args)


def addZoomaTerm(studyID, Property_type, Property_value, url):
    '''
    :param studyID: studyID
    :param Property_type: Term to be annotated
    :param Property_value: annotation value
    :param url: annotation url
    :return: Nan
    '''
    zooma_path = app.config.get("MTBLS_ZOOMA_FILE")
    zooma_df = pd.read_csv(zooma_path, sep='\t')
    lastID = int(zooma_df.iloc[-1]['BIOENTITY'].split('_')[1])
    bioentity = 'metabo_' + str(lastID + 1)
    t = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    temp = {'STUDY': studyID, 'BIOENTITY': bioentity, 'PROPERTY_TYPE': Property_type, 'PROPERTY_VALUE': Property_value,
            'SEMANTIC_TAG': url, 'ANNOTATOR': 'Jiakang Chang', 'ANNOTATION_DATE': t}
    zooma_df = zooma_df.append(temp, ignore_index=True)
    zooma_df.to_csv(zooma_path, sep='\t', index=False)


def addEntity(new_term, supclass, definition=None):
    '''
    add new term to the ontology and save it

    :param ontoPath: Ontology Path
    :param supclass:  superclass/branch name or iri of new term
    :param definition (optional): definition of the new term
    '''

    def getid(onto):
        """
        this method usd for get the last un-take continuously term ID
        :param onto: ontology
        :return: the last id for the new term
        """

        temp = []
        for c in onto.classes():
            if str(c).lower().startswith('metabolights'):
                temp.append(str(c))

        last = max(temp)
        temp = str(int(last[-6:]) + 1).zfill(6)
        id = 'MTBLS_' + temp
        return id

    try:
        onto = get_ontology(app.config.get('MTBLS_ONTOLOGY_FILE')).load()

    except Exception as e:
        print('fail to load MTBLS ontoloty from ' + app.config.get('MTBLS_ONTOLOGY_FILE'))
        logger.info(e.args)
        abort(400)
        return []

    id = getid(onto)
    namespace = onto.get_namespace('http://www.ebi.ac.uk/metabolights/ontology/')

    with namespace:
        cls = onto.search_one(label=supclass)
        if cls is None:
            cls = onto.search_one(iri=supclass)
        if cls is None:
            logger.info(f"Can't find superclass named {supclass}")
            print(f"Can't find superclass named {supclass}")
            abort(400)
            return []

        newEntity = types.new_class(id, (cls,))
        newEntity.label = new_term
        if definition != None:
            newEntity.isDefinedBy = definition
        else:
            pass

        onto.save(file=app.config.get('MTBLS_ONTOLOGY_FILE'), format='rdfxml')
