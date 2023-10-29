from __future__ import print_function

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']


def create_connection():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)
    return service


def list_files():
    service = create_connection()
    try:
        # Call the Drive v3 API
        results = service.files().list(q="'1Kvwjfbf9khOFEn6D6wvwSDfkAw3oaG4W' in parents",
            pageSize=10, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            print('No files found.')
            return
        print('Files:')
        for item in items:
            print(u'{0} ({1})'.format(item['name'], item['id']))
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print(f'An error occurred: {error}')


def upload_media_file(file):
    service = create_connection()
    try:
        media = MediaIoBaseUpload(file["data"],
                                mimetype='image/png')
        # pylint: disable=maybe-no-member
        file = service.files().create(body=file["metadata"], media_body=media,
                                      fields='id').execute()
    except HttpError as error:
        print(F'An error occurred: {error}')
        file = None

    return file.get('id')


def create_folder(file):
    service = create_connection()
    try:
        file['metadata']['mimeType'] = 'application/vnd.google-apps.folder'
        file = service.files().create(body=file["metadata"],
                                      fields='id').execute()
    except HttpError as error:
        print(F'An error occurred: {error}')
        return None

    return file.get('id')
