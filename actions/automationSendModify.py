import requests
import urllib3
from st2common.runners.base_action import Action

class RemedyModifyIncidentAPI(object):
    def __init__(self,url,userName,pwd):
        self.url = url
        self.userName = userName
        self.pwd = pwd
        self.token = ""


    #获取token
    def getToken(self):
        url = f"{self.url}/api/jwt/login"
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        data = {"username": self.userName, "password": self.pwd}
        try:
            urllib3.disable_warnings()
            token = requests.post(url=url, data=data, headers=headers, verify=False).text
        except Exception as e:
            print(222,e)
            return ["getToken error:%s" % e,"n"]
        self.token = ["AR-JWT " + token, "y"]
        return self.token

    # modify tickets
    def modifyTickets(self, TicktID, Summary, Notes, ASCPY, ASORG, ASGRP, ASCHG, Priority, INCStatus, Resolution,
                       Status_Reason, Root_Cause,workInfor,types):
        """

        @param TicktID: 单据号
        @param Summary: 描述
        @param Notes: 提示
        @param ASCPY: 公司
        @param ASORG: 组织
        @param ASGRP: 组
        @param ASCHG: itcode
        @param Priority: 级别
        @param INCStatus: 状态
        @param Resolution: 解决方案
        @param Status_Reason:
        @param Root_Cause: 12
        @param work_infor: ITSM附加信息
        @param types: 类型
        @return: []
        """
        try:
            self.getToken()
            url = f"{self.url}/api/arsys/v1/entry/Lenovo_Mobility_Interface_INC_Info"
            print(3333,self.token)
            if self.token[0] == "Get token exception":
                return self.token

            if types == "modify":
                # Alarm level conversion
                if Priority == "Disaster":
                    Priority = 0
                elif Priority == "High":
                    Priority = 1
                elif Priority == "Medium":
                    Priority = 2
                elif Priority == "Low":
                    Priority = 3


                # Alarm status conversion
                if INCStatus == "Assigned":
                    INCStatus = 1
                elif INCStatus == "In Progress":
                    INCStatus = 2
                elif INCStatus == "Pending":
                    INCStatus = 3
                elif INCStatus == "Resolved":
                    INCStatus = 4
                elif INCStatus == "Closed":
                    INCStatus = 5
                elif INCStatus == "Cancelled":
                    INCStatus = 6
                    Status_Reason = ""


                data = dict(values={
                    "TicktID": TicktID,
                    "Summary": Summary,
                    "Notes": Notes,
                    "ASCPY": ASCPY,
                    "ASORG": ASORG,
                    "ASGRP": ASGRP,
                    "ASLOGID__c": ASCHG,
                    "Reported_System": 12,
                    "INCStatus": INCStatus,
                    "Resolution": Resolution,
                    "Status_Reason": Status_Reason,
                    "Priority": Priority,
                    "Root Cause": Root_Cause,
                })
                if workInfor:
                    data["values"].update({"WorkinfoSummary":workInfor})
            else:
                data = {"values":{"TicktID":TicktID,"WorkinfoSummary":workInfor}}

            headers = {"Content-Type": "application/json; charset=UTF-8", "Authorization": self.token[0]}
            urllib3.disable_warnings()
            r = requests.post(url=url, json=data, headers=headers, verify=False)
            status_code = r.status_code
            if status_code == 201:
                print("成功...")
                return ["y", "y"]
            else:
                except_result = str(r.json())
                return ["n", except_result]

        except Exception as e:
            print(666,e.__traceback__.tb_lineno)
            return ["n","转单发生未知异常%s" % str(e)]


class ModifyTickets(Action):
    def run(self,url,userName,pwd,TicktID, Summary, Notes, ASCPY, ASORG, ASGRP, ASCHG, Priority, INCStatus, Resolution,
                       StatusReason, RootCause,workInfor,types):

        obj = RemedyModifyIncidentAPI(url,userName,pwd)

        return obj.modifyTickets(TicktID, Summary, Notes, ASCPY, ASORG, ASGRP, ASCHG, Priority, INCStatus, Resolution,
                       StatusReason, RootCause,workInfor,types)
