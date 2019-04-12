import logging, pandas as pd, os
import numpy as np
import requests
import cirpy
import ssl
from flask import request, abort, current_app as app
from flask_restful import Resource, reqparse
from flask_restful_swagger import swagger
from pubchempy import get_compounds
from app.ws.mtblsWSclient import WsClient
from app.ws.utils import read_tsv, write_tsv
from app.ws.mtbls_maf import totuples, get_table_header
from app.ws.isaApiClient import IsaApiClient
from app.ws.study_files import get_all_files_from_filesystem

logger = logging.getLogger('wslog')
# MetaboLights (Java-Based) WebService client
wsc = WsClient()
iac = IsaApiClient()


def split_rows(maf_df):
    # Split rows with pipe-lines "|"
    new_maf = pd.DataFrame(explode(explode(explode(maf_df.values, 0), 1), 2), columns=maf_df.columns)
    return new_maf


def explode(v, i, sep='|'):
    v = v.astype(str)
    n, m = v.shape
    a = v[:, i]
    bslc = np.r_[0:i, i + 1:m]
    asrt = np.append(i, bslc).argsort()
    b = v[:, bslc]
    a = np.core.defchararray.split(a, sep)
    A = np.concatenate(a)[:, None]
    counts = [len(x) for x in a.tolist()]
    rpt = np.arange(n).repeat(counts)
    return np.concatenate([A, b[rpt]], axis=1)[:, asrt]


def check_maf_for_pipes(study_location, annotation_file_name):
    annotation_file_name = os.path.join(study_location, annotation_file_name)
    try:
        maf_df = read_tsv(annotation_file_name)
    except FileNotFoundError:
        abort(400, "The file " + annotation_file_name + " was not found")
    maf_len = len(maf_df.index)

    # Any rows to split?
    new_maf_df = split_rows(maf_df)
    new_maf_len = len(new_maf_df.index)

    if maf_len != new_maf_len:  # We did find |, so we create a new MAF
        write_tsv(new_maf_df, annotation_file_name + ".split")

    return maf_df, maf_len, new_maf_df, new_maf_len


def search_and_update_maf(study_location, annotation_file_name):
    short_file_name = os.path.join(study_location, annotation_file_name.replace('.tsv', ''))
    annotation_file_name = os.path.join(study_location, annotation_file_name)
    pd.options.mode.chained_assignment = None  # default='warn'
    try:
        maf_df = read_tsv(annotation_file_name)
    except FileNotFoundError:
        abort(400, "The file " + annotation_file_name + " was not found")
    maf_len = len(maf_df.index)

    # Any rows to split?
    new_maf_df = split_rows(maf_df)
    new_maf_len = len(new_maf_df.index)

    if maf_len != new_maf_len:  # We did find | so we have to use the new dataframe
        maf_df = new_maf_df

    standard_maf_columns = {"database_identifier": 0, "chemical_formula": 1, "smiles": 2, "inchi": 3}
    maf_compound_name_column = "metabolite_identification"

    # Remove existing row values first, because that's what we do ;-)
    for column_name in standard_maf_columns:
        maf_df.iloc[:, standard_maf_columns[column_name]] = ""

    pubchem_df = create_pubchem_df(maf_df)

    row_idx = 0
    # Search using the compound name column
    for idx, comp_name in enumerate(maf_df[maf_compound_name_column]):
        print(comp_name)
        chebi_found = False
        comp_name = comp_name.rstrip()  # Remove trailing spaces

        if '/' in comp_name:  # Not a real name
            comp_name = comp_name.replace('/', ' ')

        search_res = wsc.get_maf_search("name", comp_name)  # This is the standard MetaboLights aka Plugin search
        if search_res['content']:
            name = None
            result = search_res['content'][0]
            database_identifier = result["databaseId"]
            chemical_formula = result["formula"]
            smiles = result["smiles"]
            inchi = result["inchi"]
            name = result["name"]

            pubchem_df.iloc[row_idx, 0] = database_identifier
            pubchem_df.iloc[row_idx, 1] = chemical_formula
            pubchem_df.iloc[row_idx, 2] = smiles
            pubchem_df.iloc[row_idx, 3] = inchi
            # 4 is name / metabolite_identification from MAF

            if name:
                if database_identifier:
                    if database_identifier.startswith('CHEBI:'):
                        chebi_found = True
                    maf_df.iloc[row_idx, int(standard_maf_columns['database_identifier'])] = database_identifier
                if chemical_formula:
                    maf_df.iloc[row_idx, int(standard_maf_columns['chemical_formula'])] = chemical_formula
                if smiles:
                    maf_df.iloc[row_idx, int(standard_maf_columns['smiles'])] = smiles
                if inchi:
                    maf_df.iloc[row_idx, int(standard_maf_columns['inchi'])] = inchi

        if not chebi_found:  # We could not find this in ChEBI, let's try other sources
            pc_name, pc_inchi, pc_inchi_key, pc_smiles, pc_cid, pc_formula, pc_synonyms = pubchem_search(comp_name)

            cactus_stdinchikey = cactus_search(comp_name, 'stdinchikey')
            opsin_stdinchikey = opsin_search(comp_name, 'stdinchikey')
            cactus_smiles = cactus_search(comp_name, 'smiles')
            opsin_smiles = opsin_search(comp_name, 'smiles')
            cactus_inchi = cactus_search(comp_name, 'stdinchi')
            opsin_inchi = opsin_search(comp_name, 'stdinchi')
            cactus_synonyms = cactus_search(comp_name, 'names')  # Synonyms
            csid = get_csid(pc_inchi_key, cactus_stdinchikey)

            pubchem_df.iloc[row_idx, 5] = pc_name  # 5 PubChem name
            pubchem_df.iloc[row_idx, 6] = pc_cid   # 6 PubChem CID

            if not pc_cid:
                pc_cid = get_pubchem_cid_on_inchikey(cactus_stdinchikey, opsin_stdinchikey)
            pubchem_df.iloc[row_idx, 7] = pc_cid  # 7 PubChem CID, if none get from InChIKey search (Cactus, OBSIN)
            pubchem_df.iloc[row_idx, 8] = csid  # 8 ChemSpider ID (CSID) from INCHI
            pubchem_df.iloc[row_idx, 9] = get_ranked_values(pc_smiles, cactus_smiles, opsin_smiles, None)  # 9 final smiles
            pubchem_df.iloc[row_idx, 10] = get_ranked_values(pc_inchi, cactus_inchi, opsin_inchi, None)  # 10 final inchi
            pubchem_df.iloc[row_idx, 11] = get_ranked_values(pc_inchi_key, cactus_stdinchikey,
                                                             opsin_stdinchikey, None)  # 11 final inchikey
            pubchem_df.iloc[row_idx, 12] = pc_smiles  # 12 pc_smiles
            pubchem_df.iloc[row_idx, 13] = cactus_smiles   # 13 cactus_smiles
            pubchem_df.iloc[row_idx, 14] = opsin_smiles  # 14 opsin_smiles
            pubchem_df.iloc[row_idx, 15] = pc_inchi  # 15 PubChem inchi
            pubchem_df.iloc[row_idx, 16] = cactus_inchi  # 16 Cacus inchi
            pubchem_df.iloc[row_idx, 17] = opsin_inchi   # 17 Opsin inchi
            pubchem_df.iloc[row_idx, 18] = pc_inchi_key  # 18 PubChem stdinchikey
            pubchem_df.iloc[row_idx, 19] = cactus_stdinchikey  # 19 cactus_stdinchikey
            pubchem_df.iloc[row_idx, 20] = opsin_stdinchikey   # 20 opsin_stdinchikey
            pubchem_df.iloc[row_idx, 21] = pc_formula   # 21 PubChem formula
            pubchem_df.iloc[row_idx, 22] = pc_synonyms  # 22 PubChem synonyms
            pubchem_df.iloc[row_idx, 23] = cactus_synonyms  # 23 Cactus synonyms

        row_idx += 1

    write_tsv(maf_df, short_file_name + "_annotated.tsv")
    write_tsv(pubchem_df, short_file_name + "_pubchem.tsv")

    return maf_df, maf_len, new_maf_df, new_maf_len


def get_csid(inchikey1, inchikey2):
    csid = ""
    csurl_base = 'http://parts.chemspider.com/JSON.ashx?op='

    if [inchikey1, inchikey2]:
        for inchikey in [inchikey1, inchikey2]:
            if inchikey:
                url1 = csurl_base + 'SimpleSearch&searchOptions.QueryText=' + inchikey
                resp1 = requests.get(url1)
                if resp1.status_code == 200:
                    url2 = csurl_base + 'GetSearchResult&rid=' + resp1.text
                    resp2 = requests.get(url2)
                    if resp2.status_code == 200:
                        csid = resp2.text
                        return csid.replace('[', '').replace(']', '')
    return csid


def get_pubchem_cid_on_inchikey(inchikey1, inchikey2):
    pc_cid = ''
    for inchikey in [inchikey1, inchikey2]:
        if inchikey:
            pc_name, pc_inchi, pc_inchi_key, pc_smiles, pc_cid, pc_formula, pc_synonyms = \
                pubchem_search(inchikey, search_type='inchikey')
            if pc_cid:
                return pc_cid
    return pc_cid


def get_ranked_values(pubchem, cactus, opsin, chemspider):
    if pubchem:
        return pubchem
    elif cactus:
        return cactus
    elif opsin:
        return opsin
    elif chemspider:
        return chemspider
    else:
        return ""


def create_pubchem_df(maf_df):
    # These are simply the fixed spreadsheet column headers
    pubchem_df = maf_df[['database_identifier', 'chemical_formula', 'smiles', 'inchi', 'metabolite_identification']]
    pubchem_df['iupac_name'] = ''       # 5
    pubchem_df['pubchem_cid'] = ''      # 6
    pubchem_df['pubchem_cid_ik'] = ''   # 7  PubChem CID from InChIKey search (Cactus, OBSIN)
    pubchem_df['csid_ik'] = ''          # 8  ChemSpider ID (CSID) from INCHIKEY

    pubchem_df['final_smiles'] = ''     # 9
    pubchem_df['final_inchi'] = ''      # 10
    pubchem_df['final_inchi_key'] = ''  # 11

    pubchem_df['pubchem_smiles'] = ''   # 12
    pubchem_df['cactus_smiles'] = ''    # 13
    pubchem_df['opsin_smiles'] = ''     # 14

    pubchem_df['pubchem_inchi'] = ''    # 15
    pubchem_df['cactus_inchi'] = ''     # 16
    pubchem_df['opsin_inchi'] = ''      # 17

    pubchem_df['pubchem_inchi_key'] = ''    # 18
    pubchem_df['cactus_inchi_key'] = ''     # 19
    pubchem_df['opsin_inchi_key'] = ''      # 20

    pubchem_df['pubchem_formula'] = ''      # 21
    pubchem_df['pubchem_synonyms'] = ''  # 22
    pubchem_df['cactus_synonyms'] = ''  # 23

    return pubchem_df


def opsin_search(comp_name, req_type):
    result = ""
    opsing_url = 'https://opsin.ch.cam.ac.uk/opsin/'
    url = opsing_url + comp_name + '.json'
    resp = requests.get(url)
    if resp.status_code == 200:
        json_resp = resp.json()
        result = json_resp[req_type]
    return result


def cactus_search(comp_name, type):
    result = cirpy.resolve(comp_name, type)
    synonyms = ""
    if result:
        if type == 'stdinchikey':
            return result.replace('InChIKey=', '')
        if type == 'names':
            for synonym in result:
                if get_relevant_synonym(synonym):
                    synonyms = synonyms + ';' + synonym
            return synonyms

    return result


def get_relevant_synonym(synonym):

    if synonym.startswith('CAS-'):
        synonym = synonym.replace('CAS-', '').replace('-', '')
        return is_correct_int(synonym, 6)

    elif synonym.startswith('HMDB'):
        return is_correct_int(synonym.replace('HMDB', ''), 7)

    elif synonym.startswith('LM'):  # LipidMaps
        synonym = synonym[4:]
        return is_correct_int(synonym, 8)

    elif synonym.startswith('YMDB'):
        return is_correct_int(synonym.replace('YMDB', ''), 5)

    elif synonym.startswith('ECMDB'):
        return is_correct_int(synonym.replace('ECMDB', ''), 5)

    elif synonym.startswith('ECMDB'):
        return is_correct_int(synonym.replace('ECMDB', ''), 5)

    elif synonym.startswith('C'):  # KEGG Compound
        return is_correct_int(synonym.replace('C', ''), 5)

    elif synonym.startswith('D'):  # KEGG Drug
        return is_correct_int(synonym.replace('D', ''), 5)

    elif synonym.startswith('G'):  # KEGG Glycan
        return is_correct_int(synonym.replace('G', ''), 5)

    elif synonym.startswith('R'):  # KEGG Reaction
        return is_correct_int(synonym.replace('R', ''), 5)

    elif synonym.startswith('HSDB '):  # HSDB/TOXNET
        return is_correct_int(synonym.replace('HSDB ', ''), 4)

    else:
        return False


def is_correct_int(num, length):
    try:
        if len(num) == length:
            int(num)
            return True
    except:
        return False
    return False


def pubchem_search(comp_name, search_type='name'):
    iupac = ''
    inchi = ''
    inchi_key = ''
    smiles = ''
    cid = ''
    formula = ''
    synonyms = ''

    # For this to work on Mac, run: cd "/Applications/Python 3.6/"; sudo "./Install Certificates.command
    try:
        ssl._create_default_https_context = ssl._create_unverified_context  # ToDo, get root certificates installed
        pubchem_compound = get_compounds(comp_name, namespace=search_type)
        compound = pubchem_compound[0]  # Only read the first record from PubChem = preferred entry
        inchi = compound.inchi
        inchi_key = compound.inchikey
        smiles = compound.canonical_smiles
        iupac = compound.iupac_name
        cid = compound.cid
        formula = compound.molecular_formula
        for synonym in compound.synonyms:
            if get_relevant_synonym(synonym):
                synonyms = synonyms + ';' + synonym
        logger.debug('Searching PubChem for "' + comp_name + '", got cid "' + cid + '" and iupac name "' + iupac + '"')
    except Exception as e:
        logger.error("Unable to search PubChem for compound " + comp_name)
        logger.error(e)

    return iupac, inchi, inchi_key, smiles, cid, formula, synonyms


class SplitMaf(Resource):
    @swagger.operation(
        summary="MAF pipeline splitter (curator only)",
        nickname="Add rows based on pipeline splitting",
        notes="Split a given Metabolite Annotation File based on pipelines in cells. "
              "A new MAF will be created with extension '.split'. "
              "If no annotation_file_name is given, all MAF in the study is processed",
        parameters=[
            {
                "name": "study_id",
                "description": "MTBLS Identifier",
                "required": True,
                "allowMultiple": False,
                "paramType": "path",
                "dataType": "string"
            },
            {
                "name": "annotation_file_name",
                "description": "Metabolite Annotation File name",
                "required": False,
                "allowEmptyValue": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string"
            },
            {
                "name": "user_token",
                "description": "User API token",
                "paramType": "header",
                "type": "string",
                "required": True,
                "allowMultiple": False
            }
        ],
        responseMessages=[
            {
                "code": 200,
                "message": "OK. The Metabolite Annotation File (MAF) is returned"
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
    def post(self, study_id):

        # param validation
        if study_id is None:
            abort(404, 'Please provide valid parameter for study identifier')

        # User authentication
        user_token = None
        if "user_token" in request.headers:
            user_token = request.headers["user_token"]

        # check for access rights
        is_curator, read_access, write_access, obfuscation_code, study_location, release_date, submission_date, \
            study_status = wsc.get_permissions(study_id, user_token)
        if not is_curator:
            abort(403)

        # query validation
        parser = reqparse.RequestParser()
        parser.add_argument('annotation_file_name', help="Metabolite Annotation File", location="args")
        args = parser.parse_args()
        annotation_file_name = args['annotation_file_name']

        if annotation_file_name is None:
            # Loop through all m_*_v2_maf.tsv files
            study_files, upload_files, upload_diff, upload_location = \
                get_all_files_from_filesystem(
                    study_id, obfuscation_code, study_location, directory=None, include_raw_data=False)
            maf_count = 0
            maf_changed = 0
            for file in study_files:
                file_name = file['file']
                if file_name.startswith('m_') and file_name.endswith('_v2_maf.tsv'):
                    maf_count += 1
                    maf_df, maf_len, new_maf_df, new_maf_len = check_maf_for_pipes(study_location, file_name)
                    if maf_len != new_maf_len:
                        maf_changed += 1
        else:
            maf_df, maf_len, new_maf_df, new_maf_len = check_maf_for_pipes(study_location, annotation_file_name)
            # Dict for the data (rows)
            df_data_dict = totuples(new_maf_df.reset_index(), 'rows')
            # Get an indexed header row
            df_header = get_table_header(new_maf_df)

            return {"maf_rows": maf_len, "new_maf_rows": new_maf_len, "header": df_header, "data": df_data_dict}

        return {"success": str(maf_count) + " MAF files checked for pipelines, " +
                           str(maf_changed) + " files needed updating."}


class SearchNamesMaf(Resource):
    @swagger.operation(
        summary="Search using compound names in MAF (curator only)",
        nickname="Search compound names",
        notes="Search and populate a given Metabolite Annotation File based on the 'metabolite_identification' column. "
              "New MAF files will be created with extensions '_annotated.tsv' and '_pubchem.tsv'. "
              "If no annotation_file_name is given, all MAF in the study is processed",
        parameters=[
            {
                "name": "study_id",
                "description": "MTBLS Identifier",
                "required": True,
                "allowMultiple": False,
                "paramType": "path",
                "dataType": "string"
            },
            {
                "name": "annotation_file_name",
                "description": "Metabolite Annotation File name",
                "required": False,
                "allowEmptyValue": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string"
            },
            {
                "name": "user_token",
                "description": "User API token",
                "paramType": "header",
                "type": "string",
                "required": True,
                "allowMultiple": False
            }
        ],
        responseMessages=[
            {
                "code": 200,
                "message": "OK. The Metabolite Annotation File (MAF) is returned"
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
    def post(self, study_id):

        # param validation
        if study_id is None:
            abort(404, 'Please provide valid parameter for study identifier')

        # User authentication
        user_token = None
        if "user_token" in request.headers:
            user_token = request.headers["user_token"]

        # check for access rights
        is_curator, read_access, write_access, obfuscation_code, study_location, release_date, submission_date, \
            study_status = wsc.get_permissions(study_id, user_token)
        if not is_curator:
            abort(403)

        # query validation
        parser = reqparse.RequestParser()
        parser.add_argument('annotation_file_name', help="Metabolite Annotation File", location="args")
        args = parser.parse_args()
        annotation_file_name = args['annotation_file_name']

        if annotation_file_name is None:
            # Loop through all m_*_v2_maf.tsv files
            study_files, upload_files, upload_diff, upload_location = \
                get_all_files_from_filesystem(
                    study_id, obfuscation_code, study_location, directory=None, include_raw_data=False)
            maf_count = 0
            maf_changed = 0
            for file in study_files:
                file_name = file['file']
                if file_name.startswith('m_') and file_name.endswith('_v2_maf.tsv'):
                    maf_count += 1
                    maf_df, maf_len, new_maf_df, new_maf_len = search_and_update_maf(study_location, file_name)
                    if maf_len != new_maf_len:
                        maf_changed += 1
        else:
            maf_df, maf_len, new_maf_df, new_maf_len = search_and_update_maf(study_location, annotation_file_name)
            # Dict for the data (rows)
            df_data_dict = totuples(new_maf_df.reset_index(), 'rows')
            # Get an indexed header row
            df_header = get_table_header(new_maf_df)

            return {"in_maf_rows": maf_len, "out_maf_rows": new_maf_len, "header": df_header, "data": df_data_dict}

        return {"success": str(maf_count) + " MAF files checked for pipelines, " +
                           str(maf_changed) + " files needed updating."}
