#  EMBL-EBI MetaboLights - https://www.ebi.ac.uk/metabolights
#  Metabolomics team
#
#  European Bioinformatics Institute (EMBL-EBI), European Molecular Biology Laboratory, Wellcome Genome Campus, Hinxton, Cambridge CB10 1SD, United Kingdom
#
#  Last modified: 2019-Mar-21
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

import json
import logging
import ssl
import types
from urllib.parse import quote_plus

import pandas as pd
from flask import current_app as app
from owlready2 import get_ontology, urllib, IRIS

logger = logging.getLogger('wslog')


class entity():
    def __init__(self, name, iri='', ontoName='', provenance_name='', provenance_uri='',
                 Zooma_confidence='', definition=''):

        self.name = name
        self.iri = iri
        self.ontoName = ontoName
        self.provenance_name = provenance_name
        self.Zooma_confidence = Zooma_confidence
        self.definition = definition

    def getOntoInfo(self, iri):
        try:
            url = 'https://www.ebi.ac.uk/ols/api/terms/findByIdAndIsDefiningOntology?iri=' + iri
            fp = urllib.request.urlopen(url)
            content = fp.read().decode('utf-8')
            j_content = json.loads(content)

            ontoName = j_content['_embedded']['terms'][0]['ontology_prefix']
            ontoURL = j_content['_embedded']['terms'][0]['ontology_iri']
            definition = j_content['_embedded']['terms'][0]["description"]

            return ontoName, ontoURL, definition
        except:
            return '', '', ''


class factor():
    def __init__(self, studyID, name, type, iri):
        self.studyID = studyID
        self.name = name
        self.type = type
        self.iri = iri


class Descriptor():
    def __init__(self, studyID, design_type, iri):
        self.studyID = studyID
        self.design_type = design_type
        self.iri = iri


def addEntity(ontoPath, new_term, supclass, definition=None):
    '''
        add new term to the ontology and save it

        :param ontoPath: Ontology Path
        :param new_term: new entity to be added
        :param supclass:  superclass/branch name or iri of new term
        :param definition (optional): definition of the new term
        '''

    def getid(onto):
        '''
        this method usd for get the last un-take continuously term ID
        :param onto: ontology
        :return: the last id for the new term
        '''

        temp = []
        for c in onto.classes():
            print(str(c))
            if str(c).lower().startswith('metabolights'):
                temp.append(str(c))

        last = max(temp)
        temp = str(int(last[-6:]) + 1).zfill(6)
        id = 'MTBLS_' + temp

        return id

    try:
        onto = get_ontology(ontoPath).load()
        id = getid(onto)
        namespace = onto.get_namespace('http://www.ebi.ac.uk/metabolights/ontology/')

        with namespace:
            try:
                cls = onto.search_one(label=supclass)
            except:
                try:
                    cls = onto.search_one(iri=supclass)
                except Exception as e:
                    print(e)

            newEntity = types.new_class(id, (cls,))
            newEntity.label = new_term
            if definition != None:
                newEntity.isDefinedBy = definition
            else:
                pass

        onto.save(file=ontoPath, format='rdfxml')

    except Exception as e:
        print(e)


def OLSbranchSearch(keyword, branchName, ontoName):
    res = []
    if keyword in [None, '']:
        return res

    def getStartIRI(start, ontoName):
        url = 'https://www.ebi.ac.uk/ols/api/search?q=' + start + '&ontology=' + ontoName + '&queryFields=label'
        fp = urllib.request.urlopen(url)
        content = fp.read().decode('utf-8')
        json_str = json.loads(content)
        res = json_str['response']['docs'][0]['iri']
        return urllib.parse.quote_plus(res)

    branchIRI = getStartIRI(branchName, ontoName)
    keyword = keyword.replace(' ', '%20')
    url = 'https://www.ebi.ac.uk/ols/api/search?q=' + keyword + '&rows=10&ontology=' + ontoName + '&allChildrenOf=' + branchIRI
    # print(url)
    fp = urllib.request.urlopen(url)
    content = fp.read().decode('utf-8')
    json_str = json.loads(content)

    for ele in json_str['response']['docs']:
        enti = entity(name=ele['label'],
                      iri=ele['iri'], ontoName=ontoName, provenance_name=ontoName)

        res.append(enti)
    return res


def getMetaboTerm(keyword, branch, mapping=''):
    try:
        onto = get_ontology(app.config.get('MTBLS_ONTOLOGY_FILE')).load()
    except:
        logger.info("Fail to load ontology from {path}".format(path=app.config.get('MTBLS_ONTOLOGY_FILE')))
        return None

    result = []
    cls = []

    if keyword not in [None, '']:
        # exact match
        try:
            cls += onto.search(label=keyword, _case_sensitive=False)
        except:
            logger.info("Can't find {term} in MTBLS ontology, continue...".format(term=keyword))
            print("Can't find {term} in MTBLS ontology, continue...".format(term=keyword))
            pass

        if mapping != 'exact':
            # fuzzy match
            try:
                cls += onto.search(label=keyword + '*', _case_sensitive=False)
            except:
                logger.info("Can't find terms similar with {term} in MTBLS ontology, continue...".format(term=keyword))
                print("Can't find terms similar with {term} in MTBLS ontology, continue...".format(term=keyword))

        if len(cls) == 0:
            return []

        if branch not in [None, '']:  # term = 1 , branch = 1, search branch
            try:
                sup = onto.search_one(label=branch, _case_sensitive=False)
                logger.info("Search {term} in MTBLS ontology {branch}".format(term=keyword, branch=branch))
                print("Search {term} in MTBLS ontology {branch}".format(term=keyword, branch=branch))
            except:
                logger.info("Can't find a branch called " + branch)
                print("Can't find a branch called " + branch)
                return []

            subs = sup.descendants()
            try:
                subs.remove(sup)
            except:
                pass
            result += list(set(subs) & set(cls))

            # synonym match
            if branch == 'taxonomy' or branch == 'factors':
                for cls in subs:
                    try:
                        map = IRIS['http://www.geneontology.org/formats/oboInOwl#hasExactSynonym']
                        Synonym = list(map[cls])
                        if keyword.lower() in [syn.lower() for syn in Synonym]:
                            result.append(cls)
                    except Exception as e:
                        pass

        else:  # term =1 branch = 0, search whole ontology
            result += cls

    else:  # term = None
        if branch not in [None, '']:  # term = 0, branch = 1, return whole ontology
            logger.info("Search Metabolights ontology whole {branch} branch ... ".format(branch=branch))
            print("Search Metabolights ontology whole {branch} branch ... ".format(branch=branch))

            try:
                sup = onto.search_one(label=branch, _case_sensitive=False)
                sub = sup.descendants()
                try:
                    sub.remove(sup)
                except:
                    pass

                result += sub

                # Change entity priority
                if branch == 'design descriptor' and keyword in [None, '']:
                    first_priority_terms = ['ultra-performance liquid chromatography-mass spectrometry',
                                            'untargeted metabolites', 'targeted metabolites']

                    for term in first_priority_terms:
                        temp = onto.search_one(label=term, _case_sensitive=False)
                        result.remove(temp)
                        result = [temp] + result

                result = result[:20]

            except Exception as e:
                print(e)
                logger.info("Can't find a branch called " + branch)
                print("Can't find a branch called " + branch)
                return []
        else:  # term = None, branch = None
            return []

    res = []

    for cls in result:
        enti = entity(name=cls.label[0], iri=cls.iri,
                      provenance_name='Metabolights')

        if cls.isDefinedBy:
            enti.definition = cls.isDefinedBy[0]

        if 'MTBLS' in cls.iri:
            enti.ontoName = 'MTBLS'

        else:
            try:
                onto_name = getOnto_Name(enti.iri)[0]
            except:
                onto_name = ''

            enti.ontoName = onto_name
            enti.provenance_name = onto_name

        res.append(enti)

    # OLS branch search
    if branch == 'instruments':
        if keyword in [None, '']:
            res += OLSbranchSearch('*', 'instrument', 'msio')
        else:
            res += OLSbranchSearch(keyword, 'instrument', 'msio')
    elif branch == 'column type':
        if keyword in [None, '']:
            res += OLSbranchSearch('*', 'chromatography', 'chmo')
        else:
            res += OLSbranchSearch(keyword, 'chromatography', 'chmo')

    return res


def getMetaboZoomaTerm(keyword, mapping):
    logger.info('Searching Metabolights-zooma.tsv')
    print('Searching Metabolights-zooma.tsv')
    res = []

    if keyword in [None, '']:
        return res

    try:
        fileName = app.config.get('MTBLS_ZOOMA_FILE')  # metabolights_zooma.tsv
        df = pd.read_csv(fileName, sep="\t", header=0, encoding='utf-8')
        df = df.drop_duplicates(subset='PROPERTY_VALUE', keep="last")

        if mapping == 'exact':
            temp = df.loc[df['PROPERTY_VALUE'].str.lower() == keyword.lower()]
        else:
            temp1 = df.loc[df['PROPERTY_VALUE'].str.lower() == keyword.lower()]
            reg = "^" + keyword + "+"
            temp2 = df.loc[df['PROPERTY_VALUE'].str.contains(reg, case=False)]
            frame = [temp1, temp2]
            temp = pd.concat(frame).reset_index(drop=True)

        temp = temp.drop_duplicates(subset='PROPERTY_VALUE', keep="last", inplace=False)

        for i in range(len(temp)):
            iri = temp.iloc[i]['SEMANTIC_TAG']
            # name = ' '.join(
            #     [w.capitalize() if w.islower() else w for w in temp.iloc[i]['PROPERTY_VALUE'].split()])

            name = temp.iloc[i]['PROPERTY_VALUE'].capitalize()
            obo_ID = iri.rsplit('/', 1)[-1]

            enti = entity(name=name,
                          iri=iri,
                          provenance_name='metabolights-zooma',
                          provenance_uri='https://www.ebi.ac.uk/metabolights/',
                          Zooma_confidence='High')

            try:
                enti.ontoName, enti.definition = getOnto_Name(iri)
            except:
                enti.ontoName = 'MTBLS'

            res.append(enti)
    except Exception as e:
        logger.error('Fail to load metabolights-zooma.tsv' + str(e))

    return res


def getZoomaTerm(keyword, mapping=''):
    logger.info('Requesting Zooma...')
    print('Requesting Zooma...')
    res = []

    if keyword in [None, '']:
        return res

    try:
        # url = 'http://snarf.ebi.ac.uk:8480/spot/zooma/v2/api/services/annotate?propertyValue=' + keyword.replace(' ',"+")
        url = 'https://www.ebi.ac.uk/spot/zooma/v2/api/services/annotate?propertyValue=' + keyword.replace(' ', "+")
        # url = 'https://www.ebi.ac.uk/spot/zooma/v2/api/services/annotate?propertyValue=' + keyword.replace(' ', "+")
        ssl._create_default_https_context = ssl._create_unverified_context
        fp = urllib.request.urlopen(url)
        content = fp.read().decode('utf8')
        json_str = json.loads(content)
        for term in json_str:
            iri = term['semanticTags'][0]

            # name = ' '.join(
            #     [w.capitalize() if w.islower() else w for w in term["annotatedProperty"]['propertyValue'].split()])

            name = term["annotatedProperty"]['propertyValue'].capitalize()

            if mapping == 'exact' and name != keyword:
                continue

            enti = entity(name=name,
                          iri=iri,
                          Zooma_confidence=term['confidence'])

            if enti.ontoName == '':
                enti.ontoName, enti.definition = getOnto_Name(iri)

            try:
                enti.provenance_name = term['derivedFrom']['provenance']['source']['name']
            except:
                enti.provenance_name = enti.ontoName

            if enti.provenance_name == 'metabolights':
                res = [enti] + res
            else:
                res.append(enti)

            if len(res) >= 10:
                break
    except Exception as e:
        logger.error('getZooma' + str(e))
    return res


def getOLSTerm(keyword, map, ontology=''):
    logger.info('Requesting OLS...')
    print('Requesting OLS...')
    res = []

    if keyword in [None, '']:
        return res

    try:
        # https://www.ebi.ac.uk/ols/api/search?q=lung&groupField=true&queryFields=label,synonym&fieldList=iri,label,short_form,obo_id,ontology_name,ontology_prefix
        url = 'https://www.ebi.ac.uk/ols/api/search?q=' + keyword.replace(' ', "+") + \
              '&groupField=true' \
              '&queryFields=label,synonym' \
              '&type=class' \
              '&fieldList=iri,label,short_form,ontology_name,description,ontology_prefix' \
              '&rows=30'  # &exact=true
        if map == 'exact':
            url += '&exact=true'

        if ontology not in [None, '']:
            onto_list = ','.join(ontology)
            url += '&ontology=' + onto_list

        fp = urllib.request.urlopen(url)
        content = fp.read().decode('utf-8')
        j_content = json.loads(content)
        responses = j_content["response"]['docs']

        for term in responses:
            # name = ' '.join([w.capitalize() if w.islower() else w for w in term['label'].split()])

            name = term['label'].capitalize()

            try:
                definition = term['description'][0]
            except:
                definition = ''

            try:
                ontoName, provenance_name = getOnto_Name(term['iri'])
            except:
                ontoName = ''
                provenance_name = ''

            enti = entity(name=name, iri=term['iri'], definition=definition, ontoName=ontoName,
                          provenance_name=provenance_name)

            res.append(enti)
            if len(res) >= 20:
                break

    except Exception as e:
        print(e.args)
        logger.error('getOLS' + str(e))
    return res


def getBioportalTerm(keyword):
    logger.info('Requesting Bioportal...')
    print('Requesting Bioportal...')
    res = []

    if keyword in [None, '']:
        return res

    try:
        url = 'http://data.bioontology.org/search?q=' + keyword.replace(' ', "+")  # + '&require_exact_match=true'
        request = urllib.request.Request(url)
        request.add_header('Authorization', 'apikey token=' + app.config.get('BIOPORTAL_TOKEN'))
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
            elif 'meddra' in iri.lower():
                ontoName = 'MEDDRA'
            else:
                ontoName = getOnto_Name(iri)[0]

            enti = entity(name=term['prefLabel'],
                          iri=iri,
                          ontoName=ontoName, provenance_name=ontoName)
            res.append(enti)
            iri_record.append(iri)
            if len(res) >= 5:
                break
    except Exception as e:
        logger.error('getBioportal' + str(e))
    return res


def getWormsTerm(keyword):
    logger.info('Requesting WoRMs ...')
    print('Requesting WoRMs ...')

    res = []
    if keyword in [None, '']:
        return res

    try:
        url = 'http://www.marinespecies.org/rest/AphiaRecordsByName/{keyword}?like=true&marine_only=true&offset=1'.format(
            keyword=keyword.replace(' ', '%20'))
        fp = urllib.request.urlopen(url)
        content = fp.read().decode('utf-8')
        j_content = json.loads(content)

        for term in j_content:
            if term["scientificname"] != None and term["url"] != None:
                name = term["scientificname"]
                iri = term["url"]
                definition = term["authority"]
                ontoName = 'WoRMs'
                provenance_name = 'World Register of Marine Species'

                enti = entity(name=name, iri=iri, definition=definition, ontoName=ontoName,
                              provenance_name=provenance_name)
                res.append(enti)

            if len(res) >= 10:
                break
    except Exception as e:
        logger.error(str(e))

    return res


def getWoRMsID(term):
    try:
        url = 'http://www.marinespecies.org/rest/AphiaIDByName/' + term.replace(' ', '%20') + "?marine_only=true"
        fp = urllib.request.urlopen(url)
        AphiaID = fp.read().decode('utf-8')
        if AphiaID != '-999':
            return AphiaID
        return ''
    except:
        return ''


def getOnto_info(pre_fix):
    '''
     get ontology information include  "name", "file", "version", "description"
     :param pre_fix: ontology prefix
     :return: "ontology iri", "version", "ontology description"
     '''
    try:
        url = 'https://www.ebi.ac.uk/ols/api/ontologies/' + pre_fix
        fp = urllib.request.urlopen(url)
        content = fp.read().decode('utf-8')
        j_content = json.loads(content)

        iri = j_content['config']['id']
        version = j_content['config']['version']
        description = j_content['config']['title']
        return iri, version, description
    except:
        if pre_fix == "MTBLS":
            return 'http://www.ebi.ac.uk/metabolights/ontology', '1.0', 'EBI Metabolights ontology'
        return '', '', ''


def getOnto_Name(iri):
    # get ontology name by giving iri of entity
    try:
        url = 'http://www.ebi.ac.uk/ols/api/terms/findByIdAndIsDefiningOntology?iri=' + iri
        fp = urllib.request.urlopen(url)
        content = fp.read().decode('utf-8')
        j_content = json.loads(content)
        try:
            return j_content['_embedded']['terms'][0]['ontology_prefix'], \
                   j_content['_embedded']['terms'][0]['description'][0]
        except:
            return j_content['_embedded']['terms'][0]['ontology_prefix'], ''
    except:
        if 'MTBLS' in iri:
            return 'MTBLS', 'Metabolights ontology'
        elif 'BAO' in iri:
            return 'BAO', 'BioAssay Ontology'
        else:
            substring = iri.rsplit('/', 1)[-1]
            return ''.join(x for x in substring if x.isalpha()), ''


def getOnto_version(pre_fix):
    try:
        url = 'https://www.ebi.ac.uk/ols/api/ontologies/' + pre_fix
        fp = urllib.request.urlopen(url)
        content = fp.read().decode('utf-8')
        j_content = json.loads(content)
        return j_content['config']['version']
    except:
        return ''


def getOnto_url(pre_fix):
    try:
        url = 'https://www.ebi.ac.uk/ols/api/ontologies/' + pre_fix
        fp = urllib.request.urlopen(url)
        content = fp.read().decode('utf-8')
        j_content = json.loads(content)
        return j_content['config']['id']
    except:
        return ''


def setPriority(res_list, priority):
    res = sorted(res_list, key=lambda x: priority.get(x.ontoName, 1000))
    return res


def reorder(res_list, keyword):
    def sort_key(s, keyword):
        try:
            exact = s.lower() == keyword.lower()
        except:
            exact = False

        try:
            start = s.startswith(keyword)
        except:
            start = False
        try:
            partial = keyword in s
        except:
            partial = False

        return exact, start, partial

    try:
        res = sorted(res_list, key=lambda x: sort_key(x.name, keyword), reverse=True)
        return res
    except:
        return res_list


def removeDuplicated(res_list):
    iri_pool = []
    for res in res_list:
        if res.iri in iri_pool:
            res_list.remove(res)
        else:
            iri_pool.append(res.iri)
    return res_list


def getDescriptionURL(ontoName, iri):
    ir = quote_plus(quote_plus(iri))
    url = 'https://www.ebi.ac.uk/ols/api/ontologies/' + ontoName + '/terms/' + ir
    return url
