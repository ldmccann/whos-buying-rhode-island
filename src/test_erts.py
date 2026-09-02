import requests

url = "https://ricampaignfinance.com/RIPublic/Reporting/TransactionReport.aspx"

params = {
    "OrgID": "9385",
    "BeginDate": "01/01/2026",
    "EndDate": "03/31/2026",
    "LastName": "",
    "FirstName": "",
    "ContType": "0",
    "State": "",
    "City": "",
    "ZIPCode": "",
    "EmployerName": "",
    "Amount": "0",
    "ReportType": "Contrib",
    "CFStatus": "F",
    "MPFStatus": "A",
    "Level": "S",
    "SumBy": "Type",
    "Sort1": "ReceiptDate",
    "Direct1": "desc",
    "Sort2": "None",
    "Direct2": "asc",
    "Sort3": "None",
    "Direct3": "asc",
    "Site": "Public",
    "Incomplete": "A",
    "ContSource": "CF",
}

response = requests.get(url, params=params)

print("Status:", response.status_code)
print("URL:", response.url)
print("Response length:", len(response.text))
print()
print(response.text[:1000])
