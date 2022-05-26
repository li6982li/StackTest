def

if dMsg['Submitter'] in ['niulx2', 'tiandj1', 'chenlei16', 'shihy4', 'huangjie5', 'wahmad']:
    return None
from automationP1 import SmsTtsCallP1

call_obj = SmsTtsCallP1()
call_obj.ali_call_number(dMsg['Incident ID'], "01057870297")