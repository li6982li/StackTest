
import datetime
import logging
import time
from qcloudsms_py import SmsSingleSender
from qcloudsms_py.httpclient import HTTPError
import random

from st2common.runners.base_action import Action


def sms_template_parameters(msg1, msg2):
    """
    Parameter format required to generate Tencent Cloud SMS template
    """
    incident_no = "单据号:" + ""
    priority = "级别:" + ""
    alert_content = "告警:" + ""
    incident_no = str(incident_no)
    priority = str(priority)
    alert_content = str(alert_content)
    alert_datas = '\n' + alert_content + '\n' + priority + '\n' + incident_no
    sender_data = [msg1,"",msg2,]
    return sender_data



class SendSingleSms(Action):

    def run(self, phoneNum,smsMsg1,smsMsg2,APPID ,APPKEY ,TEMPLATE_IDS ,SMS_SIGN ,SMS_CODE_REDIS_EXPIRES):
        try:
            APPID = int(APPID)
            # Generate 4-digit random extension code extend
            extend = random.randint(0, 9999)
            # Add 0 in front of less than 4
            # SMS used to track and locate the corresponding alarm
            extend = "%03d" % extend
            content = sms_template_parameters(smsMsg1,smsMsg2)
            ssender = SmsSingleSender(APPID, APPKEY)
            try:
                _Ret = ssender.send_with_param(86, phoneNum, TEMPLATE_IDS, content, SMS_SIGN, extend=extend,ext="")
            except HTTPError as e:
                return {"errmsg": "sms HTTPError:%s" % e}
            except Exception as e:
                return {"errmsg": "sms error:%s" % e}
            else:

                errmsg = _Ret.get('errmsg')
                sid = _Ret.get('sid')
                fee = _Ret.get('fee',0)
                expense = str(float(fee) * 0.028)
                if _Ret.get("result") == 0:
                    sms_results = ["Success","send SMS Success"]
                else:
                    sms_results =["Failed",errmsg]
                return sms_results
        except Exception as e:
            return ["Failed","sendMessages error:%s" % e]




