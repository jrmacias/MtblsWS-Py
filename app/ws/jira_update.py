#  EMBL-EBI MetaboLights - https://www.ebi.ac.uk/metabolights
#  Metabolomics team
#
#  European Bioinformatics Institute (EMBL-EBI), European Molecular Biology Laboratory, Wellcome Genome Campus, Hinxton, Cambridge CB10 1SD, United Kingdom
#
#  Last modified: 2020-Jan-17
#  Modified by:   kenneth
#
#  Copyright 2020 EMBL - European Bioinformatics Institute
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

import gspread
import pandas as pd
from flask import request, abort, current_app as app, jsonify
from flask_restful import Resource
from flask_restful_swagger import swagger
from jira import JIRA
from oauth2client.service_account import ServiceAccountCredentials

from app.ws.db_connection import get_all_studies
from app.ws.mtblsWSclient import WsClient
from app.ws.utils import safe_str

# https://jira.readthedocs.io
options = {
    'server': 'https://www.ebi.ac.uk/panda/jira/'}
logger = logging.getLogger('wslog')
wsc = WsClient()
project = 12732  # The id for the 'METLIGHT' project
curation_epic = 'METLIGHT-1'  # id 10236 'METLIGHT-1 Epic'
curation_lable = 'curation'


class Jira(Resource):
    @swagger.operation(
        summary="Create (or update) Jira tickets for MetaboLights study curation (curator only)",
        parameters=[
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
                "message": "OK."
            },
            {
                "code": 401,
                "message": "Unauthorized. Access to the resource requires user authentication. "
                           "Please provide a study id and a valid user token"
            },
            {
                "code": 403,
                "message": "Forbidden. Access to the study is not allowed. Please provide a valid user token"
            },
            {
                "code": 404,
                "message": "Not found. The requested identifier is not valid or does not exist."
            }
        ]
    )
    def put(self):
        user_token = None
        # User authentication
        if "user_token" in request.headers:
            user_token = request.headers["user_token"]

        if user_token is None:
            abort(401)

        # param validation
        is_curator, read_access, write_access, obfuscation_code, study_location, release_date, submission_date, \
            study_status = wsc.get_permissions('MTBLS3', user_token)
        if not is_curator:
            abort(403)

        status, message, updated_studies_list = update_or_create_jira_issue(user_token, is_curator)

        if status:
            return {'Success': message}
        else:
            return {'Error': message}


def update_or_create_jira_issue(user_token, is_curator):
    try:
        params = app.config.get('JIRA_PARAMS')
        user_name = params['username']
        password = params['password']

        updated_studies = []
        try:
            jira = JIRA(options=options, basic_auth=(user_name, password))
        except:
            return False, 'Could not connect to JIRA server, incorrect username or password?', updated_studies

        # Get the MetaboLights project
        mtbls_project = jira.project(project)

        if is_curator:
            studies = get_all_studies(user_token)

        for study in studies:
            study_id = None
            user_name = None
            release_date = None
            update_date = None
            study_status = None
            curator = None
            status_change = None
            curation_due_date = None

            try:
                study_id = safe_str(study[0])
                user_name = safe_str(study[1])
                release_date = safe_str(study[2])
                update_date = safe_str(study[3])
                study_status = safe_str(study[4])
                curator = safe_str(study[5])
                status_change = safe_str(study[6])
                curation_due_date = safe_str(study[7])
            except Exception as e:
                logger.error(str(e))
            issue = []
            summary = None

            # date is 'YYYY-MM-DD HH24:MI'
            due_date = status_change[:10]

            logger.info('Updating Jira ticket/Google Calendar for ' + study_id + '. Values: ' +
                        user_name + '|' + release_date + '|' + update_date + '|' + study_status + '|' +
                        curator + '|' + status_change + '|' + due_date)

            # Get an issue based on a study accession search pattern
            search_param = "project='" + mtbls_project.key + "' AND summary  ~ '" + study_id + " \\\-\\\ 20*'"
            issues = jira.search_issues(search_param)  # project = MetaboLights AND summary ~ 'MTBLS121 '
            new_summary = study_id + ' - ' + release_date.replace('-', '') + ' - ' + \
                          study_status + ' (' + user_name + ')'
            try:
                if issues:
                    issue = issues[0]
                else:
                    if study_status == 'Submitted' or study_status == 'In Curation':
                        logger.info("Could not find Jira issue for " + search_param)
                        print("Creating new Jira issue for " + search_param)
                        issue = jira.create_issue(project=mtbls_project.key, summary='MTBLS study - To be updated',
                                                  description='Created by API', issuetype={'name': 'Story'})
                    else:
                        continue  # Only create new cases if the study is in status Submitted/In Curation
            except Exception:  # We could not find or create a Jira issue
                continue

            summary = issue.fields.summary  # Follow pattern 'MTBLS123 - YYYYMMDD - Status'
            try:
                assignee = issue.fields.assignee.name
            except:
                assignee = ""

            valid_curator = False
            jira_curator = ""
            if curator:
                if curator.lower() == 'mark':
                    jira_curator = 'mwilliam'
                    valid_curator = True
                elif curator.lower() == 'keeva':
                    jira_curator = 'keeva'
                    valid_curator = True
            else:
                jira_curator = ""

            if not status_change:
                status_change = "No status changed date reported"
            # Release date or status has changed, or the assignee (curator) has changed
            if summary.startswith('MTBLS') and (summary != new_summary or assignee != jira_curator):

                # Add "Curation" Epic
                issues_to_add = [issue.key]
                jira.add_issues_to_epic(curation_epic, issues_to_add)  # Add the Curation Epic
                labels = maintain_jira_labels(issue, study_status, user_name)

                # Add a comment to the issue.
                comment_text = 'Current status ' + study_status + '. Status last changed date ' + status_change + \
                               '. Curation due date ' + due_date + '. Database update date ' + update_date
                jira.add_comment(issue, comment_text)

                # Change the issue's summary, comments and description.
                issue.update(summary=new_summary, fields={"labels": labels}, notify=False)

                if valid_curator:  # ToDo, what if the curation log is not up to date?
                    issue.update(assignee={'name': jira_curator})

                updated_studies.append(study_id)
                logger.info('Updated Jira case for study ' + study_id)
                print('Updated Jira case for study ' + study_id)
    except Exception as e:
        logger.error("Jira updated failed for " + study_id + ". " + str(e))
        return False, 'Update failed: ' + str(e), str(study_id)
    return True, 'Ticket(s) updated successfully', updated_studies


def maintain_jira_labels(issue, study_status, user_name):
    # Add the 'curation' label if needed
    labels = issue.fields.labels

    submitted_flag = False
    curation_flag = False
    in_curation_flag = False
    inreview_flag = False
    metabolon_flag = False
    placeholder_flag = False
    metaspace_flag = False
    submitted_label = 'submitted'
    curation_label = 'curation'
    in_curation_label = 'in_curation'
    inreview_label = 'in_review'
    metabolon_label = 'metabolon'
    placeholder_label = 'placeholder'
    metaspace_label = 'metaspace'

    for i in labels:
        if i == submitted_label:
            submitted_flag = True
        elif i == curation_label:
            curation_flag = True
        elif i == in_curation_label:
            in_curation_flag = True
        elif i == inreview_label:
            inreview_flag = True
        elif i == metabolon_label:
            metabolon_flag = True
        elif i == placeholder_label:
            placeholder_flag = True
        elif i == metaspace_label:
            metaspace_flag = True

    if not curation_flag:  # Do not confuse with the In Curation status, this is a "curator tasks" flag
        labels.append(curation_label)

    if study_status == 'Submitted' and not submitted_flag:  # The "Submitted" label is not present
        labels.append(submitted_label)

    if study_status == 'In Curation':
        if not in_curation_flag:  # The "in_curation" label is not present
            labels.append(in_curation_label)
        if submitted_flag:
            labels.remove(submitted_label)

    if study_status == 'In Review':
        if not inreview_flag:  # The "in_review" label is not present
            labels.append(inreview_label)
        if in_curation_flag:
            labels.remove(in_curation_label)

    if study_status == 'Public':  # The "in_review" label should now be replaced
        if inreview_flag:
            labels.remove(inreview_label)
        if in_curation_flag:
            labels.remove(in_curation_label)
        labels.append('public')

    if "Placeholder" in user_name and not placeholder_flag:
        labels.append(placeholder_label)

    if "Metabolon" in user_name and not metabolon_flag:
        labels.append(metabolon_label)

    if "Metaspace" in user_name and not metaspace_flag:
        labels.append(metaspace_label)

    return labels


class GoogleDocs(Resource):
    @swagger.operation(
        summary="Read database for curation status (curator only)",
        notes="Read the database table for curation status",
        parameters=[
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
                "message": "OK."
            },
            {
                "code": 401,
                "message": "Unauthorized. Access to the resource requires user authentication. "
                           "Please provide a valid user token"
            }
        ]
    )
    def get(self):

        user_token = None

        # User authentication
        if "user_token" in request.headers:
            user_token = request.headers["user_token"]

        if user_token is None:
            abort(401)

        is_curator, read_access, write_access, obfuscation_code, study_location, release_date, submission_date, \
            study_status = wsc.get_permissions('MTBLS1', user_token)
        if not is_curator:
            abort(401)

        data = self.get_curation_log()

        return jsonify(data)

    def get_curation_log(self):
        # Load spreadsheet from Google sheet
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        google_creds = app.config.get('GOOGLE_CREDS')
        google_json = json.loads(google_creds, encoding='utf-8')
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(google_json, scopes=scope)
        gc = gspread.authorize(credentials)
        query_wks = gc.open('MTBLS Curation Status Log').get_worksheet(5)  # "Database query" sheet
        query_records = query_wks.get_all_records()

        update_wks = gc.open('MTBLS Curation Status Log').get_worksheet(6)  # "Database update" sheet
        update_records = update_wks.get_all_records()
        for updates in update_records:
            print(updates[1])

        df = pd.DataFrame(query_records)
        return df
