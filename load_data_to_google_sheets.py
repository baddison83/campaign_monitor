import gspread
import os
import queries as q
import snowflake.connector

from datetime import date
from decimal import Decimal
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

SNOW_USER = os.getenv('SNOWFLAKE_USERNAME')
SNOW_PASS = os.getenv('SNOWFLAKE_PASSWORD')
SNOW_ACCOUNT = os.getenv('SNOWFLAKE_ACCOUNT')
SNOW_WH = os.getenv('SNOWFLAKE_WAREHOUSE')

def connect_to_snowflake(db='BIZ_DEV', sch='CAMPAIGN_REPORTS'):
    conn = snowflake.connector.connect(
        user=SNOW_USER,
        password=SNOW_PASS,
        account=SNOW_ACCOUNT,
        warehouse=SNOW_WH,
        database=db,
        schema=sch
    )

    return conn


def get_google_client():
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    credentials_file = os.getenv('GS_CREDS')
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    return gspread.authorize(creds)


def job_params():
    return {
        'facts': {'query': q.FACTS,
                'sheet': 'FACTS'},
        'specs': {'query': q.SPECS,
                  'sheet': 'SPECS'},
        'guars': {'query': q.GUARS,
                  'sheet': 'GUARANTEES'},
        'cm360': {'query': q.CM360,
                  'sheet': 'CM360'}
    }


def main():
    # snowflake connection
    connection = connect_to_snowflake()
    cursor = connection.cursor()

    # gsheet auth
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    client = get_google_client()

    params = job_params()

    for k in params.keys():
        query = params.get(k).get('query')
        sheet_name = params.get(k).get('sheet')

        cursor.execute(query)
        rows = cursor.fetchall()

        sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
        sheet.clear()  # clear data currently in sheet

        # Write column names
        headers = [desc[0] for desc in cursor.description]
        sheet.append_row(headers)

        # Write in batches. Need this to work around gsheet api limits
        batch_size = 1000
        batch = []

        # write rows
        for row in rows:
            # convert date objects to string
            row = [val.isoformat() if isinstance(val, date) else val for val in row]
            # convert Decimal objects to float
            row = [float(val) if isinstance(val, Decimal) else val for val in row]
            batch.append(list(row))

            # if the batch is full, write append it to the sheet
            if len(batch) >= batch_size:
                sheet.append_rows(batch)
                batch = []  # reset

        # Write append any leftover rows in the batch
        if batch:
            sheet.append_rows(batch)


    # close snowflake connection
    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()
