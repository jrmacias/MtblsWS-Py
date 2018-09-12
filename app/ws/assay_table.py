import logging, json, pandas as pd, numpy as np
from flask import request, abort, jsonify
from flask_restful import Resource, reqparse
from flask_restful_swagger import swagger
from app.ws.mtblsWSclient import WsClient

"""
MTBLS Assay Tables

Manage the Assays from a MTBLS studies.
"""

logger = logging.getLogger('wslog')
# MetaboLights (Java-Based) WebService client
wsc = WsClient()


# Convert panda DataFrame to json tuples object
def totuples(df, text):
    d = [
        dict([
            (colname, row[i])
            for i, colname in enumerate(df.columns)
        ])
        for row in df.values
    ]
    return {text: d}


def get_table_header(table_df):
    # Get an indexed header row
    df_header = pd.DataFrame(list(table_df))  # Get the header row only
    df_header = df_header.reset_index().to_dict(orient='list')
    mapping = {}
    print(df_header)
    for i in range(0, len(df_header['index'])):
        mapping[df_header[0][i]] = df_header['index'][i]
    return mapping


def insert_row(idx, df, df_insert):
    return df.iloc[:idx, ].append(df_insert, ignore_index=True).append(df.iloc[idx:, ]).reset_index(drop=True)


class AssayTable(Resource):
    """Create Assay for a given study"""
    @swagger.operation(
        summary="Update Assay table cells for a given study",
        nickname="Update Assay table cells",
        notes="Update Assay table cells for a given Study.",
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
                "name": "assay_file_name",
                "description": "Assay File name",
                "required": True,
                "allowMultiple": False,
                "paramType": "path",
                "dataType": "string"
            },
            {
                "name": "row_num",
                "description": "The row number of the cell to update (exclude header)",
                "required": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "integer"
            },
            {
                "name": "column_name",
                "description": "The column name of the cell to update",
                "required": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string"
            },
            {
                "name": "cell_value",
                "description": "The value of the cell to update",
                "required": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string"
            },
            {
                "name": "user_token",
                "description": "User API token",
                "paramType": "header",
                "type": "string",
                "required": False,
                "allowMultiple": False
            }
        ],
        responseMessages=[
            {
                "code": 200,
                "message": "OK. The Assay Table has been updated."
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
    def put(self, study_id, assay_file_name):
        parser = reqparse.RequestParser()
        parser.add_argument('row_num', help="The row number of the cell to update (exclude header)")
        parser.add_argument('column_name', help="The column name of the cell to update")
        parser.add_argument('cell_value', help="The column name of the cell to update")
        row_num = None
        column_name = None
        cell_value = None
        if request.args:
            args = parser.parse_args(req=request)
            row_num = args['row_num']
            column_name = args['column_name']
            cell_value = args['cell_value']

        # param validation
        if study_id is None or assay_file_name is None or row_num is None or column_name is None:
            abort(404)

        # User authentication
        user_token = None
        if "user_token" in request.headers:
            user_token = request.headers["user_token"]

        # check for access rights
        if not wsc.get_permisions(study_id, user_token)[wsc.CAN_WRITE]:
            abort(403)

        study_path = wsc.get_study_location(study_id, user_token)
        assay_file_name = study_path + "/" + assay_file_name

        assay_df = pd.read_csv(assay_file_name, sep="\t", header=0, encoding='utf-8')
        assay_df = assay_df.replace(np.nan, '', regex=True)

        try:
            row = int(row_num)
            column = assay_df.columns.get_loc(column_name)
            assay_df.iloc[row, column] = cell_value
        except Exception:
            logger.warning('Could not find row (' + row_num + '( and/or column (' + column_name + ') in the table')

        # Write the new empty columns back in the file
        assay_df.to_csv(assay_file_name, sep="\t", encoding='utf-8', index=False)

        # Convert panda DataFrame (single row) to json tuples object
        def totuples(df, rown):
            d = [
                dict([
                    (colname, row[rown])
                    for rown, colname in enumerate(df.columns)
                ])
                for row in df.values
            ]
            return {'assaydata': d}

        df_dict = totuples(assay_df.reset_index(), row)

        return df_dict


class ReadAssayFile(Resource):
    @swagger.operation(
        summary="Get Assay table for a study using assay filename",
        nickname="Get Assay table for a given study",
        notes="Get a given Assay table for a MTBLS Study with in JSON format.",
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
                "name": "assay_file_name",
                "description": "Assay file name",
                "required": True,
                "allowMultiple": False,
                "paramType": "path",
                "dataType": "string"
            },
            {
                "name": "user_token",
                "description": "User API token",
                "paramType": "header",
                "type": "string",
                "required": False,
                "allowMultiple": False
            }
        ],
        responseMessages=[
            {
                "code": 200,
                "message": "OK. The Assay table is returned"
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
    def get(self, study_id, assay_file_name):
        # param validation
        if study_id is None or assay_file_name is None:
            logger.info('No study_id and/or assay file name given')
            abort(404)

        # User authentication
        user_token = None
        if "user_token" in request.headers:
            user_token = request.headers["user_token"]

        logger.info('Assay Table: Getting ISA-JSON Study %s, using API-Key %s', study_id, user_token)
        # check for access rights
        if not wsc.get_permisions(study_id, user_token)[wsc.CAN_READ]:
            abort(403)

        study_path = wsc.get_study_location(study_id, user_token)
        assay_file_name = study_path + "/" + assay_file_name
        logger.info('Trying to load Assay (%s) for Study %s', assay_file_name, study_id)
        # Get the Assay table or create a new one if it does not already exist
        assay_df = pd.read_csv(assay_file_name, sep="\t", header=0, encoding='utf-8')
        # Get rid of empty numerical values
        assay_df = assay_df.replace(np.nan, '', regex=True)

        df_data_dict = totuples(assay_df.reset_index(), 'rows')

        # Get an indexed header row
        df_header = get_table_header(assay_df)

        return {'assayHeader': df_header, 'assayData': df_data_dict}

    @swagger.operation(
        summary="Add a new row to the given Assay file",
        nickname="Add Assay table row",
        notes="Update an Assay table for a given Study.",
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
                "name": "assay_file_name",
                "description": "Assay File name",
                "required": True,
                "allowMultiple": False,
                "paramType": "path",
                "dataType": "string"
            },
            {
                "name": "new_row",
                "description": "The row to add to the assay file",
                "required": True,
                "allowMultiple": False,
                "paramType": "body",
                "dataType": "string"
            },
            {
                "name": "user_token",
                "description": "User API token",
                "paramType": "header",
                "type": "string",
                "required": False,
                "allowMultiple": False
            }
        ],
        responseMessages=[
            {
                "code": 200,
                "message": "OK. The Assay table has been updated."
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
    def post(self, study_id, assay_file_name):

        try:
            data_dict = json.loads(request.data.decode('utf-8'))
            new_row = data_dict['assayData']  # Use "index:n" element from the (JSON) row, this is the original row number
        except (KeyError):
            new_row = None

        if new_row is None:
            abort(404, "Please provide valid data for updated new row(s). "
                       "The JSON string has to have a 'assayData' element")

        for element in new_row:
            element.pop('index', None)  #Remove "index:n" element from the (JSON) row, this is the original row number

        # param validation
        if study_id is None or assay_file_name is None:
            abort(404, 'Please provide valid parameters for study identifier and assay file name')

        # User authentication
        user_token = None
        if "user_token" in request.headers:
            user_token = request.headers["user_token"]

        # check for access rights
        if not wsc.get_permisions(study_id, user_token)[wsc.CAN_WRITE]:
            abort(403)

        study_path = wsc.get_study_location(study_id, user_token)
        assay_file_name = study_path + "/" + assay_file_name

        assay_df = pd.read_csv(assay_file_name, sep="\t", header=0, encoding='utf-8')
        assay_df = assay_df.replace(np.nan, '', regex=True)  # Remove NaN
        assay_df = assay_df.append(new_row, ignore_index=True)  # Add new row to the spreadsheet

        # Write the new row back in the file
        assay_df.to_csv(assay_file_name, sep="\t", encoding='utf-8', index=False)

        df_data_dict = totuples(assay_df.reset_index(), 'rows')

        # Get an indexed header row
        df_header = get_table_header(assay_df)

        return {'assayHeader': df_header, 'assayData': df_data_dict}

    @swagger.operation(
        summary="Update existing rows in the given Assay file",
        nickname="Update Assay rows",
        notes="Update rows in the Assay table for a given Study.",
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
                "name": "assay_file_name",
                "description": "Assay File name",
                "required": True,
                "allowMultiple": False,
                "paramType": "path",
                "dataType": "string"
            },
            {
                "name": "new_row",
                "description": "The row(s) to update in the assay file",
                "required": True,
                "allowMultiple": False,
                "paramType": "body",
                "dataType": "string"
            },
            {
                "name": "user_token",
                "description": "User API token",
                "paramType": "header",
                "type": "string",
                "required": False,
                "allowMultiple": False
            }
        ],
        responseMessages=[
            {
                "code": 200,
                "message": "OK. The Assay has been updated."
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
                "message": "Not found or missing parameters. The requested identifier is not valid or does not exist."
            }
        ]
    )
    def put(self, study_id, assay_file_name):

        # param validation
        if study_id is None or assay_file_name is None:
            abort(404, 'Please provide valid parameters for study identifier and assay file name')

        try:
            data_dict = json.loads(request.data.decode('utf-8'))
            new_rows = data_dict['assayData']  # Use "index:n" element from the (JSON) row, this is the original row number
        except (KeyError):
            new_rows = None

        if new_rows is None:
            abort(404, "Please provide valid data for updated new row(s). "
                       "The JSON string has to have a 'assayData' element")

        for row in new_rows:
            try:
                row_index = row['index']  # Check if we have a value in the row number(s)
            except (KeyError):
                row_index = None

            if new_rows is None or row_index is None:
                abort(404, "Please provide valid data for the updated row(s). "
                           "The JSON string has to have an 'index:n' element in each (JSON) row, "
                           "this is the original row number. The header row can not be updated")

        # User authentication
        user_token = None
        if "user_token" in request.headers:
            user_token = request.headers["user_token"]

        # check for access rights
        if not wsc.get_permisions(study_id, user_token)[wsc.CAN_WRITE]:
            abort(403)

        study_path = wsc.get_study_location(study_id, user_token)
        assay_file_name = study_path + "/" + assay_file_name

        assay_df = pd.read_csv(assay_file_name, sep="\t", header=0, encoding='utf-8')
        assay_df = assay_df.replace(np.nan, '', regex=True)  # Remove NaN

        for row in new_rows:
            try:
                row_index_int = int(row['index'])
            except:
                row_index_int is None

            if row_index_int is not None:
                assay_df = assay_df.drop(assay_df.index[row_index_int])  # Remove the old row from the spreadsheet
                # pop the "index:n" from the new_row before updating
                row.pop('index', None)  #Remove "index:n" element from the (JSON) row, this is the original row number
                assay_df = insert_row(row_index_int, assay_df, row)  # Update the row in the spreadsheet

        # Write the new row back in the file
        assay_df.to_csv(assay_file_name, sep="\t", encoding='utf-8', index=False)

        df_data_dict = totuples(assay_df.reset_index(), 'rows')

        # Get an indexed header row
        df_header = get_table_header(assay_df)

        return {'assayHeader': df_header, 'assayData': df_data_dict}

    @swagger.operation(
        summary="Delete a row of the given Assay file",
        nickname="Delete Assay row",
        notes="Update an Assayfor a given Study.",
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
                "name": "assay_file_name",
                "description": "Assay File name",
                "required": True,
                "allowMultiple": False,
                "paramType": "path",
                "dataType": "string"
            },
            {
                "name": "row_num",
                "description": "The row number(s) to remove, comma separated if more than one",
                "required": True,
                "allowMultiple": False,
                "paramType": "query",
                "dataType": "string"
            },
            {
                "name": "user_token",
                "description": "User API token",
                "paramType": "header",
                "type": "string",
                "required": False,
                "allowMultiple": False
            }
        ],
        responseMessages=[
            {
                "code": 200,
                "message": "OK. The Assay has been updated."
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
    def delete(self, study_id, assay_file_name):

        # query validation
        parser = reqparse.RequestParser()
        parser.add_argument('row_num', help="The row number of the cell(s) to remove (exclude header)", location="args")
        args = parser.parse_args()
        row_num = args['row_num']

        # param validation
        if study_id is None or assay_file_name is None or row_num is None:
            abort(404)

        # User authentication
        user_token = None
        if "user_token" in request.headers:
            user_token = request.headers["user_token"]

        # check for access rights
        if not wsc.get_permisions(study_id, user_token)[wsc.CAN_WRITE]:
            abort(403)

        study_path = wsc.get_study_location(study_id, user_token)
        assay_file_name = study_path + "/" + assay_file_name

        assay_df = pd.read_csv(assay_file_name, sep="\t", header=0, encoding='utf-8')
        assay_df = assay_df.replace(np.nan, '', regex=True)  # Remove NaN
        row_nums = row_num.split(",")

        # Need to remove the highest row number first as the DataFrame dynamically re-orders when one row is removed
        sorted_num_rows = [int(x) for x in row_nums]
        sorted_num_rows.sort(reverse=True)
        for num in sorted_num_rows:
            assay_df = assay_df.drop(assay_df.index[num])  # Drop row(s) in the spreadsheet

        # Write the updated file
        assay_df.to_csv(assay_file_name, sep="\t", encoding='utf-8', index=False)

        # To be sure we read the file again
        assay_df = pd.read_csv(assay_file_name, sep="\t", header=0, encoding='utf-8')
        assay_df = assay_df.replace(np.nan, '', regex=True)  # Remove NaN

        df_data_dict = totuples(assay_df.reset_index(), 'rows')

        # Get an indexed header row
        df_header = get_table_header(assay_df)

        return {'assayHeader': df_header, 'assayData': df_data_dict}

