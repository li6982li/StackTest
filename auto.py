"""
Filename:           automationNewZabbixAlert.py
Description:        automation type and actions
Create Date:        2020/09/23 09:00:00
Author:             binyao
Email:              liyn25@lenovo.com
Team Members:       Bruce Mao, Jinhui Ma, Yannan Li
Version:            1.0
Change History      Date                    Modified by                 Modified Reason
CH1                 09/23/2020              Yannan Li                Modify the code logic and optimize the code
CH2                 13/10/2020              Yannan Li                Modify the next action steps of a failed transfer order
CH3                 12/23/2020              Yannan Li                Code optimization

"""
import random
import datetime
import logging
import time
import pymysql

pymysql.install_as_MySQLdb()
from Model.automationModel import stepAndResult,masterData,serverDesk,dealyAlarms
from automationModifyTicketsApi import RemedyModifyIncidentAPI
from automationSenderSms import SendSingleSms
from automationSenderVoices import VoiceCallFlow
from automationVerification import Verification
from automationDB import write_error, write_back_status, write_tmp_tel, write_rpa
from automationSenderEmail import Mails
from automationMapping import Mapping
from addQueItem import OrchestratorAPI
from automationQuickAPI import getCcaopToken, sendCcaop, queryCcaop
from automationFilesystem import getAdminFile
import re
from automationMysqlConnect import SQLdb

from automationCMDB import getCmdb
# 1：成功
# 2：电话失败，邮件成功
# 3：转单失败或者程序失败，邮件成功 （由于还没有出现过，转单失败的也较少，所以放到一起）
# 4：邮件失败，邮件失败

class typeChoice(Verification, RemedyModifyIncidentAPI, Mapping):

    def __init__(self):
        super().__init__()
        self.num = 1;self.admin = "";self.obj=""
        self.smsResult = ["un", "00:00:00"];self.callResult = ["un", "00:00:00"]
        self.modifyResult = ["un", "00:00:00"];self.verResult = ["un", "00:00:00"]
        self.smsInfo = "";self.smsIp = "";self.smsHostName="" #短信描述;短信中ip，短信中主机名
        self.callIp = ""; self.callIncident = "" #电话中ip；电话中单据尾号信息
        self.workInfo = "";self.actionStep = "";self.netxAction = "" #单据workinfo信息；验证步骤；下一步操作
        self.emailAddress = "";self.type = "other"
        self.actions = ""

    #记录日志
    def writeError(self,aMsg,errors,times):
        logging.error(errors)
        write_error(aMsg['Incident ID'], times, aMsg["Summary"], aMsg["Priority"],str(errors))

    #action中对应的发邮件
    def sendEmail(self,aMsg):

        if "New Storage Alert" in aMsg["Summary"]:
            return self.send_email(aMsg['Incident ID'], aMsg["Priority"], aMsg["Summary"],aMsg["Notes"], "", "",[self.emailAddress], "Storage",2)
        return self.send_email(aMsg['Incident ID'], aMsg["Priority"], aMsg["Summary"],aMsg["Notes"], "", "",[self.emailAddress], "nual",1)

    # send email
    def send_email(self, incident, priority, summary,notes, stepResult, nextAction,groups, emailType,num):
        """

        @param aMsg: 单据信息
        @param step_result:执行的步骤
        @param next_action: 下一步操作
        @param modify_result: 转单结果和时间组成的列表
        @param telAdmin: 单据处理人信息
        @param IP: IP
        @return: 3表示成功，4表示失败
        """
        emailTime = datetime.datetime.now()
        logging.info(incident + str(self.admin) + "|||" + "email")
        try:
            if num ==1:
                # 发送邮件给服务台
                write_back_status(self.obj, "email-%s" % stepResult, "", nextAction, emailTime)
            eamilObj = Mails()
            emailResult = eamilObj.send_emails(incident, priority, summary,notes,stepResult, groups[-1], "", nextAction, emailType)
            if emailResult[0] == "n":
                if num < 3:
                    time.sleep(3);num += 1
                    return self.send_email(incident, priority, summary,notes, stepResult, nextAction,groups, emailType,num)
                self.writeError({'Incident ID':incident,'Priority':priority,'Summary':summary,'Notes':notes},"Email send failed please check-:%s" % emailResult[1],emailTime)
                return "4"
            return "3"
        except Exception as e:
            self.writeError({'Incident ID':incident,'Priority':priority,'Summary':summary,'Notes':notes}, "Email send failed  fun发生未知异常%s:filenum:%s" % (str(e),e.__traceback__.tb_lineno), emailTime)
            return "4"

    def duty(self, aMsg):
        try:
            times = time.strftime("%m-%d %H:%M", time.localtime(int(time.time())))
            mon_day, hour_mins = str(times).split(" ")
            """
            lesc 01-12排班:20:00-08:00 表示12号晚八点到13号早八点，
            13号早八点前，需要用12号 + 时间去匹配
            后续有其他值班组，同理，跨天到早上几点，就用那个时间判断,时间写在mapping.txt中telAdmin[1]
            注意，如果没有跨晚上00；00，那么mapping.txt中telAdmin[1]一定要填""
            """
            # 获取到mapping文件存放的值班类型以及对应分段时间点
            telAdmin = self.get_tel_admin(aMsg["Assignee"],
                                          aMsg["Summary"].split("[Solution ID:")[1].split("]")[0].strip(),
                                          aMsg['Incident ID'], aMsg["Priority"], aMsg["Summary"])
            dutyTime = telAdmin[1]  # 分段时间点
            types = telAdmin[0]
            if isinstance(dutyTime, dict) == True:  # 表示ludp值班类型
                note = eval(aMsg["Notes"])  # ludp的note是个字典
                itcode = note.get("it_code")  # 获取itcode
                if itcode in ["group","NONE","None"] or not itcode:
                    itcode = ""
                dutyTime = dutyTime.get(note.get("Support_Group_name", "Support_Group_name"))  # ludp类型的分段时间点
                if not dutyTime:  # 不是BI和operation值班表，直接拨打note里面的电话
                    self.admin = [note.get("Support_Company"), note.get("Support_Organization"),
                            note.get("Support_Group_name"), itcode, note.get("telephone"), ""]
                    return "success"
                dutyTime = dutyTime[0]  # 得到最终分段时间点
                types = note.get("Support_Group_name")
            if dutyTime > hour_mins >= "00:00":  # 判断是否需要日期减一天
                mon_day = str(datetime.date.today() - datetime.timedelta(days=1)).split("-", 1)[-1]
            org = self.get_duty(types, mon_day, hour_mins, aMsg['Incident ID'], aMsg["Summary"], aMsg["Priority"])
            # 没有匹配到值班号码
            if len(org) == 9:
                self.workInfo = "未找到值班号码，请服务台同事查询并通知用户=>"
                return self.modifyAndEmailToServerDesk(aMsg)
            # 正常值班表
            elif len(org) == 6:
                self.admin = org
                return "success"
            else:
                # 表示ludp值班表
                self.admin = [note.get("Support_Company"), note.get("Support_Organization"), note.get("Support_Group_name"),itcode] + org
                return "success"
        except Exception as e:
            self.workInfo = "获取值班表时，发生异常，请服务台同事处理=>duty fun error:%s:filenum:%s" % (e,e.__traceback__.tb_lineno)
            return self.modifyAndEmailToServerDesk(aMsg)
        finally:logging.info(aMsg['Incident ID'] + "值班表" + str(self.admin))

    def verification(self, aMsg):
        try:
            self.type = "offline"
            verTime = datetime.datetime.now()
            host_name, IP = aMsg["Summary"].split('|_|')[-1].strip().split(':')
            write_back_status(self.obj, "verification-开始验证", "-|-".join(self.admin[:6]), "请ping单据中IP",verTime)
            pingResult = self.offlines(IP)
            self.workInfo = pingResult  #转单的workInfo
            self.verResult = [pingResult, verTime]
            return "success"
        except Exception as e:
            self.writeError(aMsg, "verifiction fun error:%s" % e, datetime.datetime.now())
            return "验证失败：%s" % e

    def checkPhone(self,aMsg):
        try:
            if not self.admin[4]:
                self.workInfo = "电话或短信通知，但是没有电话号码=>"
                result = self.modifyAndEmailToServerDesk(aMsg)
                result[6] = "8";return result
            phones = self.admin[4].replace("(", "").replace(")", "").replace("-", "").replace("（", "").replace(
                "）", "").replace(" ", "").replace(" ", "").replace("_", "").replace("—", "").replace("-", "")
            phone = re.findall('(1\d{10})', phones)
            if not phone:
                self.workInfo = "电话号码格式不正确：%s，请根据正确信息处理" % self.admin[4]
                result = self.modifyAndEmailToServerDesk(aMsg)
                result[6] = "8";return result
            return "success"
        except Exception as e:
            self.writeError(aMsg,"检查电话号码异常:%s：filenum:%s" % (e,e.__traceback__.tb_lineno),datetime.datetime.now())
            self.workInfo = "检查电话号码异常:%s，请根据正确信息处理" % e
            result = self.modifyAndEmailToServerDesk(aMsg)
            result[6] = "8";return result

    def sendSms(self, aMsg):
        try:
            if self.verResult[0] == "invalid alert through verification":
                return "success"
            elif aMsg["Priority"] != "High" and "w1" not in self.actions:
                return ""
            logging.info(aMsg['Incident ID'] + aMsg["Summary"].replace(" ","").split("[SolutionID:")[1].split("]")[0].strip()+str(self.admin) + "|||" + "sms")
            result = self.checkPhone(aMsg)
            if isinstance(result,list):
                return result

            if aMsg["Priority"].strip() == "High":
                priority = "P2(High)"
            elif aMsg["Priority"].strip() == "Low":
                priority = "P4(Low)"
            else:
                priority = "P3(Medium)"
            msgObj = SendSingleSms()
            self.smsResult[1] = datetime.datetime.now()
            if self.admin[0]:   #不是额外通知用户的短信，才需要记录到步骤表
                write_back_status(self.obj, "send_sms-开始发送短信:%s" % self.admin[4], "-|-".join(self.admin[:6]),"请发送短信(%s)" % (self.admin[4]),self.smsResult[1])
            msgResult = msgObj.send_sms_result(self.admin[4], self.admin[5], aMsg['Incident ID'], priority, self.smsInfo,self.smsHostName, self.smsIp)
            if msgResult[0] == "n":
                self.smsResult[0] = "n"
                self.writeError(aMsg,"发送短信%s失败原因:%s" % (self.admin[4], str(msgResult[1])),self.smsResult[1])
                return str(msgResult[1])
            self.smsResult[0] = "y"
            return "success"
        except Exception as e:
            self.smsResult[0] = "n"
            self.writeError(aMsg, "sendSms fun error:%s：%s" % (e,e.__traceback__.tb_lineno), datetime.datetime.now())
            return "sendSms fun error:%s" % e

    def sendTel(self,aMsg):
        if aMsg["Priority"] != "High" and "w3" not in self.actions:
            return ""

        elif self.verResult[0] == "invalid alert through verification":
            return "success"

        logging.info(aMsg['Incident ID'] +aMsg["Summary"].replace(" ","").split("[SolutionID:")[1].split("]")[0].strip()+ str(self.admin) + "|||" + "tel")
        result = self.checkPhone(aMsg)
        if isinstance(result, list):
            return result

        telAdmin = self.get_tel_admin(aMsg["Assignee"],self.admin[3],
                                      aMsg['Incident ID'], aMsg["Priority"], aMsg["Summary"])
        if telAdmin =="1":  #压缩告警
            try:
                admins = "|_|".join(self.admin[:6]) + "|_|new"
                result = write_tmp_tel(aMsg, admins, self.smsInfo, self.smsHostName, self.smsIp, 4)
                if result:
                    return [self.smsResult[0], "sun", self.modifyResult[0], self.smsResult[1], datetime.datetime.now(),
                            self.modifyResult[1], "6", self.verResult[0], self.verResult[1]]
                self.writeError(aMsg,"插入压缩电话表失败",datetime.datetime.now())
                return "插入压缩表失败"
            except Exception as e:
                self.writeError(aMsg, "dealyAlarm fun error:%s" % e, datetime.datetime.now())
                return "失败"

        try:
            self.callResult[1] = datetime.datetime.now()
            callObj = VoiceCallFlow()
            if self.admin[0]:  #不是额外通知用户才需要记录到表格
                write_back_status(self.obj, "send_tel-开始第一次拨打电话:%s" % self.admin[4], "-|-".join(self.admin[:6]),"请拨打电话(%s)" % self.admin[4], self.callResult[1])
            callResult = callObj.callResult(self.obj, aMsg['Incident ID'], self.callIp, self.callIncident,self.admin[4])
            #第一个号码失败了，并且有第二个号码
            if callResult[0] =="n" and self.admin[5] :
                self.writeError(aMsg, "拨打电话%s失败原因:%s" % (self.admin[4], str(callResult[1])), self.callResult[1])
                self.modify_tickets(aMsg['Incident ID'], "", "", "", "", "", "", "", "", "", "", "","automaiton %s打电话通知%s失败,失败原因%s" % (str(self.callResult[1]).split(".")[0], self.admin[4], str(callResult[1])),"")
                self.admin[4] = self.admin[5];self.admin[5] = ""
                #表示流程需要发送短信，否则直接拨打电话
                if self.smsResult[0] != "un":  #表示需要发送短信
                    self.sendSms(aMsg)
                return self.sendTel(aMsg)

            elif callResult[0] == "y":
                result = self.modify_tickets(aMsg['Incident ID'], "", "", "", "", "", "", "", "", "", "", "",
                                             "automaiton %s打电话通知%s" % (str(self.callResult[1]).split(".")[0], self.admin[4]), "")
                self.callResult[0] = "y"
                if result[0] == "n":
                    self.writeError(aMsg,"添加workifo信息错误：%s" % result[1], self.callResult[1])
                return "success"
            self.callResult[0] = "n"
            self.writeError(aMsg, "拨打电话%s失败原因:%s" % (self.admin[4], str(callResult[1])), self.callResult[1])
            result = self.modify_tickets(aMsg['Incident ID'], "", "", "", "", "", "", "", "", "", "", "",
                                "automaiton %s打电话通知%s失败,失败原因:%s" % (str(self.callResult[1]).split(".")[0], self.admin[4], str(callResult[1])), "")
            if result[0] == "n":
                self.writeError(aMsg, "添加workifo信息错误：%s" % result[1], self.callResult[1])
            return "拨打电话失败：%s" % callResult[1]
        except Exception as e:
            self.callResult[0] = "n"
            self.writeError(aMsg,"sendTel fun error:%s:filenum:%s" % (e,e.__traceback__.tb_lineno),self.callResult[1])
            return "电话函数失败：%s" % e

    def modifyTickets(self,aMsg):
        logging.info(aMsg['Incident ID'] + aMsg["Summary"].replace(" ","").split("[SolutionID:")[1].split("]")[0].strip()+str(self.admin) + "|||" + "modify")
        self.modifyResult[1] = datetime.datetime.now()
        try:
            if not (len(self.admin) == 4 and self.admin[2] =="Monitoring"):
                info =  "transfer_tickets-开始转单"
            else:
                info = "transfer_tickets-开始转单且%s" % self.workInfo
            write_back_status(self.obj, info, "-|-".join(self.admin[:6]),"请直接转单%s" % "-|-".join(self.admin[:4]), self.modifyResult[1])
            priority = aMsg["Priority"]
            if self.verResult[0] =="invalid alert through verification":
                priority = "Medium"
            modifyResult = self.modify_tickets(aMsg['Incident ID'], aMsg["Summary"], aMsg["Notes"], self.admin[0],
                                               self.admin[1], self.admin[2], self.admin[3], priority, aMsg["Status"],
                                               aMsg["Resolution"], "", "",self.workInfo, "modify")

            if modifyResult[0] =="n":
                self.modifyResult[0] = "n"
                self.writeError(aMsg,"转单失败:%s" % modifyResult[1],datetime.datetime.now())
                return "转单失败:%s" % modifyResult[1]
            self.modifyResult[0] = "y"
            return "success"
        except Exception as e:
            self.modifyResult[0] = "n"
            self.writeError(aMsg,"转单 fun error:%s:filenum:%s" % (e,e.__traceback__.tb_lineno),datetime.datetime.now())
            return "转单函数失败:%s" % e

    def getCmdbInfo(self,aMsg):
        try:
            self.type = "filesystem"
            host_name, IP = aMsg["Summary"].split("|_|")[-1].strip().split(':')
            dirs = aMsg["Summary"].split("volume")[-1].strip().split("|_|")[0].split(" ")[0].strip().replace(":", "")
            if str(dirs) not in ["C", "/"]:  # 非系统盘，去cmdb获取信息
                # 获取itsm中的组织信息，用于判断cmdb中获取的信息是否正确
                itsmOrg = self.get_itsm_org(aMsg['Incident ID'])
                orgAndPhone = getAdminFile(aMsg, IP, itsmOrg)
                # 返回列表，表示获取到完整的组织信息和电话，否则表示给XPO或者程序遇见未知异常
                if isinstance(orgAndPhone, list) == True:
                    self.admin = orgAndPhone
                    return "success"
                else:
                    r = self.send_email(aMsg['Incident ID'], aMsg["Priority"], aMsg["Summary"],aMsg["Notes"],orgAndPhone, "产生了一个cmdb中信息不全的非系统盘告警，请帮忙通知用户进行处理，多谢",[self.emailAddress], "filesystem",1)
                    logging.info("单据：%s solutionId:%s ==发送filesystme邮件给：%s结果：%s" % (aMsg['Incident ID'],aMsg["Summary"].replace(" ","").split("[SolutionID:")[1].split("]")[0].strip(),str(self.emailAddress),str(r)))
                    self.workInfo = "未从CMDB中获取到正确转单信息,请将单据Pending至Gisnoc账户中.等待处理.=>%s" %str(orgAndPhone)
                    result = self.modifyAndEmailToServerDesk(aMsg)
                    result[6] = "10";return result
            else:return "success"  #系统盘
        except Exception as e:
            self.writeError(aMsg,"getCmdbInfo fun error:%s:filenum:%s" % (e,e.__traceback__.tb_lineno),datetime.datetime.now())
        self.workInfo = "获取文件系统转单信息发送未知异常，请服务台同事处理单据=>"
        return self.modifyAndEmailToServerDesk(aMsg)

    def smsTelInfo(self,summary,incident,priority,notes):
        try:
            try:
                hostName,ip = summary.split("|_|")[-1].strip().split(':')  # 设备
                self.smsInfo = summary.split("Alert]")[-1].split("|_|")[0]
            except Exception as e:
                hostName,ip = "未知","未知"
                self.smsInfo = summary.split("Alert]")[-1]
            if "Solarwinds Alert" in summary:
                ip, hostName = summary.split("|_|")[-1].strip().split(':')  # 网络
                self.smsHostName = "的网络设备:%s, " % hostName
                self.smsIp = "IP:%s" % ip
                self.callIp = "IP地址为:%s的网络设备" % ip
                self.type = "network"

            elif notes.find("AppSystem:")>=0:  #统一的应用监控
                types = notes.split("AppSystem:")[1].split("]")[0]
                self.smsHostName = "的%s应用监控点" % types
                self.callIp = "%s应用监控点"% ".".join(types.replace("-",""))
                self.type = types

            elif "Splunk Alert" in summary:
                self.smsHostName = "splunk"
                self.callIp="s.p.l.u.n.k"
                self.type = "splunk"

            elif "New Storage Alert" in summary:
                self.smsHostName = "的存储设备"
                self.callIp = "存储设备"
                self.type = "stroage"

            elif "Solman Alert" in summary:
                self.smsHostName = "solman"
                self.callIp = "应用监控"
                self.type = "solman"

            elif "XClarity Alert" in summary:
                ip = summary.split("|_|")[-2].split("_")[-1]
                self.smsHostName = "的设备SN号：%s " % ip
                self.callIp = "SN号为:%s的设备" % ip
                self.type = "hardware"

            elif "Support_Organization" in notes and "job_name" in notes: #ludp & 麦哲伦单据
                notes = eval(notes)
                types = notes.get("system_name","ludp")
                self.smsHostName = "%s应用监控点，Job Name:%s" % (types,notes.get("job_name"))
                self.callIp = "%s应用监控点"% types.replace("ludp","L.U.D.P")
                self.type = types



            else:
                self.smsHostName = "的设备：%s, " % hostName
                self.smsIp = "IP:%s" % ip
                self.callIp = "IP地址为:%s的设备" % ip
            priToP = {"High":"P2","Medium":"P3","Low":"P4"}
            self.callIncident = "后四位：%s,发生%s级别的告警" % ("".join(incident)[-4:],priToP.get(priority))
            return "success"
        except Exception as e:
            self.writeError({"Incident ID":incident,"Summary":summary,"Priority":priority},"解析单据:%s-%s==中电话或者短信信息失败:%s:filenum:%s" % (incident,summary,e,e.__traceback__.tb_lineno),datetime.datetime.now())
            return "failed"

    def noticeOwn(self,aMsg):
        if "6" not in str(self.actions):
            logging.error("额外通知,但是流程中没有6" + str(aMsg["Summary"]) + str(self.actions))
            return ""
        logging.info(str(aMsg["Summary"]) + str(self.actions) + "notice11111")
        try:
            hostName, ip = aMsg["Summary"].split("|_|")[-1].strip().split(':')
            remdyInfo = getCmdb(ip)
            phones = remdyInfo["phone"]
            phones = phones.replace("(", "").replace(")", "").replace("-", "").replace("（","").replace(
                "）", "").replace(" ", "").replace(" ", "").replace("_", "").replace("—", "").replace("-", "")
            phone = re.findall('(1\d{10})', phones)[0]
            self.admin = ["","","","",phone,""]
            smsResult = self.sendSms(aMsg)
            if smsResult == "success":smsResult = "发送短信给:%s,的结果为:%s" % (phone,"成功")
            else:smsResult = "发送短信给:%s,的结果为:%s" % (phone,"失败")
            telResult = self.sendTel(aMsg)
            if telResult == "success":telResult = "拨打电话给:%s，的结果为:%s" % (phone,"成功")
            else:telResult = "拨打电话给:%s，的结果为:%s" % (phone,"失败")
        except Exception as e:
            p = remdyInfo
            if isinstance(remdyInfo,dict):
                p = remdyInfo.get("phone","cmdb中没有电话字段数据")
            self.writeError(aMsg,"noticeOwn fun error:%s==%s" % (e,p),datetime.datetime.now())
            smsResult = "没有发送短信给owner，从cmdb查到的数据:%s" % p
            telResult = "没有拨打电话给owner，从cmdb查到数据同上"
        r = self.send_email(aMsg['Incident ID'], aMsg["Priority"], aMsg["Summary"],aMsg["Notes"],smsResult,telResult,[self.emailAddress],"notice",2)
        logging.info("单据号:%s, solutionId:%s notice %s email result is %s" % (aMsg['Incident ID'],aMsg["Summary"].replace(" ","").split("[SolutionID:")[1].split("]")[0].strip(),str(self.emailAddress),str(r)))
        return ""  #额外通知own的结果不影响服务台是否干预，不用返回failed


    # rpa失败，二次推送lmac
    def rpaError(self, aMsg):
        self.workInfo = aMsg.get("workInfo","=>")
        result = self.modifyAndEmailToServerDesk(aMsg)
        result[6] = "7"
        result.append("rpa")
        return result

    #只适用于转单给服务台，失败之后，邮件给服务台
    def modifyAndEmailToServerDesk(self,aMsg):
        try:
            if aMsg.get("types", "") != "rpa":  #非rpa二次推送的单据，才记录错误信息
                self.writeError(aMsg,self.workInfo,datetime.datetime.now())
            self.workInfo = self.workInfo.split("=>")[0]
            groupObj = serverDesk.query.filter(serverDesk.fouraccounts == aMsg.get("Assignee").strip()).first()
            if not groupObj:
                return [self.smsResult[0], self.callResult[0], self.modifyResult[0], self.smsResult[1],self.callResult[1], self.modifyResult[1], "5", self.verResult[0], self.verResult[1]]
            self.admin = [groupObj.company, groupObj.org, groupObj.groups, groupObj.assignee]
            result = self.modifyTickets(aMsg)
            if result.find("失败")>=0: #转给服务台失败，在这里邮件给服务台
                r = self.send_email(aMsg['Incident ID'], aMsg["Priority"], aMsg["Summary"],aMsg["Notes"], self.workInfo, "请根据单据操作",[groupObj.emails.split("/")], "nual", 1)
                return [self.smsResult[0], self.callResult[0], self.modifyResult[0], self.smsResult[1], self.callResult[1], self.modifyResult[1],("3-%s" % r).replace("-3",""), self.verResult[0], self.verResult[1]]
        except Exception as e:
            self.writeError(aMsg,"modifyAndEmailToServerDesk fun error:%s:filenum:%s" % (e,e.__traceback__.tb_lineno),datetime.datetime.now())
        return [self.smsResult[0], self.callResult[0], self.modifyResult[0], self.smsResult[1], self.callResult[1], self.modifyResult[1],"8", self.verResult[0], self.verResult[1]]

    def cancelledResolvedTickets(self,aMsg,status,resolution,workinfo):

        return self.modify_tickets(aMsg['Incident ID'], aMsg["Summary"], aMsg["Notes"],
                            aMsg['Assigned Support Company'], aMsg["Assigned Organization"],
                            aMsg["Assigned Group"], aMsg["Assignee"], aMsg["Priority"], status,
                            resolution, "", "", workinfo, "modify")

    def autoQuicks(self, aMsg):
        times = datetime.datetime.now()
        self.type = "autoquicks"
        try:
            # return ["un", "un", "y", "00:00:00", "00:00:00",self.modifyResult[1],"1", "un", "00:00:00","y",times]
            host_name, IP = aMsg["Summary"].split('|_|')[-1].strip().split(':')
            result = sendCcaop(IP, self.admin[7])
            if str(result).find("error_") >= 0:
                self.writeError(aMsg,"quick  %s" % result,times)
                self.workInfo = "自修复失败，请手动处理单据"
                return ""  #不返回 失败，那么会按照短信转单-电话通知用户
            quickResult = queryCcaop(1,result)
            # 自修复成功，直接resolved单据
            if quickResult == "success":
                self.modifyResult[1] = datetime.datetime.now()
                r = self.resolvedTickets(aMsg,"Issue:\nReason:\nResolution:Monitoring Fixed","Auto resume", "Auto recovery")
                if r[0] == "n":
                    self.workInfo = "自修复成功，最后resolved单据失败,请直接resolved单据即可=>"
                    self.modifyAndEmailToServerDesk(aMsg)
                    return ["un", "un", "n", "00:00:00", "00:00:00",self.modifyResult[1],"3", "un", "00:00:00","y",times]
                return ["un", "un", "y", "00:00:00", "00:00:00",self.modifyResult[1],"1", "un", "00:00:00","y",times]
            self.writeError(aMsg, "quick %s" % quickResult, times)
        except Exception as e:
            self.writeError(aMsg,"quick fun发生未知异常%s:filenum:%s" % (str(e),e.__traceback__.tb_lineno),times)
        self.workInfo = "自修复失败，请手动处理单据=>"
        return ""  # 不返回 失败，那么会按照短信转单-电话通知用户

    def getCallRemark(self,incident,callRemark,priority):
        try:
            if callRemark is None:
                return "",""
            phone = re.findall('(1\d{10})', str(callRemark))
            email = callRemark.split("Email:")[-1]
            email = re.findall(".*@lenovo.com",email)
            if email:email = email[0].split("/")
            else:email = []
            if phone: phone = phone[0]
            else:phone=""
            return phone,email
        except Exception as e:
            self.writeError({'Incident ID':incident, "Summary":"callback","Priority":priority}, "解析callRemark字段异常：%s:filenum:%s" % (e,e.__traceback__.tb_lineno), datetime.datetime.now())
            return "",[]

    def dba(self,aMsg):
        self.type = "dba"
        if aMsg["Priority"].strip() != "High":
            return "success"
        obj = SQLdb("mysqlIp")

        try:
            dbDict = self.get_db_type(aMsg['Incident ID'],aMsg["Summary"], aMsg["Priority"])
            dbType = (aMsg["Summary"].split("Alert]")[-1].split("|_|")[0]).replace(" ","").lower()
            ip = aMsg["Summary"].split("|_|")[-1].split(":")[-1]
            for db,types in dbDict.items():
                if db in dbType:
                    break
            result = obj.fechdb("SELECT dbaowner_tel,dbaowner FROM dbds.zabbix_view where dbtype=%s and nodeip1=%s",[types,ip])
            if str(result).find("failed") >= 0 or not result:
                self.workInfo = "IP：%s ,dba:%s 未从dba数据库获取到单据处理人信息=>%s" % (aMsg["Summary"].split("|_|")[-1].split(":")[-1],db,str(result))
                return self.modifyAndEmailToServerDesk(aMsg)
            #dba单据，P2 的替换掉itcode和电话即可
            self.admin[3] = result[0][1];self.admin[4] = result[0][0]
            return "success"
        except Exception as e:
            self.workInfo = "IP：%s ,dba:%s 未从dba数据库获取到单据处理人信息=>%s:filenum:%s" % (aMsg["Summary"].split("|_|")[-1].split(":")[-1],db,str(e),e.__traceback__.tb_lineno)
            return self.modifyAndEmailToServerDesk(aMsg)
        finally:
            obj.closedb()

    def rpa(self,aMsg):
        self.type = "rpa"
        #插入automation_tickets_rpa表
        write_result = write_rpa(aMsg['Incident ID'],aMsg["Summary"], aMsg["Priority"],aMsg["Notes"],self.admin,aMsg['Assigned Support Company'], aMsg["Assigned Organization"], aMsg["Assigned Group"], aMsg["Assignee"])
        #失败转给服务台
        if not write_result:
            self.workInfo = "rpa单据插入数据库失败=>"
            return self.modifyAndEmailToServerDesk(aMsg)
        rpa_time = datetime.datetime.now()
        try:
            process_name = self.admin[-2];queue_name = self.admin[-1]
            orchestrator_obj = OrchestratorAPI();orchestrator_obj.getAccessToken()
            orchestrator_result = orchestrator_obj.addQueueItem(queue_name, "Normal", process_name,"Description of the process to be executed")
            # 成功回写
            if int(orchestrator_result[0]) in [200,201]:
                return ["un", "un", "un", "00:00:00", "00:00:00", "00:00:00", "6", "un", "00:00:00"]
            self.workInfo = "rpa单据触发oc流程失败=>"
            return self.modifyAndEmailToServerDesk(aMsg)
        except Exception as e:
            self.workInfo = "程序异常无法识别该单据是否触发成功，请服务台同事处理=>%s" % e
            return self.modifyAndEmailToServerDesk(aMsg)


    def resolvedTickets(self,aMsg,resolution="Issue:\nReason:\nResolution:Monitoring Fixed",
                        Status_Reason="Auto resume",Root_Cause = "Auto recovery",workinfo=""):
        return self.modify_tickets(aMsg['Incident ID'], aMsg["Summary"], aMsg["Notes"],
                            aMsg['Assigned Support Company'], aMsg["Assigned Organization"],
                            aMsg["Assigned Group"], aMsg["Assignee"], aMsg["Priority"], "Resolved",
                            resolution, Status_Reason, Root_Cause, workinfo, "modify")


    def newAutoResolvedTickets(self,aMsg):
        times = datetime.datetime.now()
        if aMsg.get("Assignee")=="auto_fix" and aMsg.get("Assigned Group") == "Automation" \
                and aMsg.get('Assigned Organization') == "CC-Monitoring":
            try:
                r = self.resolvedTickets(aMsg, "Issue:\nReason:\nResolution:Monitoring Fixed", "Auto resume","Auto recovery")
                if r[0] == "y":
                    return [self.smsResult[0], self.callResult[0], "y", self.smsResult[1], self.callResult[1],times, "1", self.verResult[0], self.verResult[1], self.type]
                self.writeError(aMsg, "自动关单失败:%s" % r[1], times)
                email = self.get_groups("autoquick",aMsg['Incident ID'], aMsg["Summary"],aMsg["Priority"])
                self.send_email(aMsg['Incident ID'], aMsg["Priority"], aMsg["Summary"], "", "resolved失败", "手动Resolved", email, "nual", 1)
            except Exception as e:
                self.writeError(aMsg, "newAutoResolvedTickets error:%s filenum:%s" % (e,e.__traceback__.tb_lineno), times)
            return [self.smsResult[0], self.callResult[0], "n", self.smsResult[1], self.callResult[1],times, "1", self.verResult[0], self.verResult[1], self.type]
        return ""


    # 单据类型选择，使用不同方法处理
    def zabbix_switch(self, aMsg):
        noticeOwner = "n"
        try:
            time.sleep(random.randint(2, 5))  # 随机等待1-4s，减少一点同时查询数据库的进程数
            self.obj = stepAndResult.query.filter(stepAndResult.incident_ID == aMsg['Incident ID'].strip()).first()
            isResolved = self.newAutoResolvedTickets(aMsg)
            if isinstance(isResolved, list) == True:
                return isResolved, ""
            funAndTag = {"0": "verification", "1": "sendSms","w1":"sendSms", "2": "modifyTickets", "3": "sendTel", "w3":"sendTel","4": "sendEmail",
                         "5": "duty", "6": "noticeOwn", "7": "getCmdbInfo", "8": "dba", "9": "autoQuicks", "10": "rpa"}
            if aMsg.get("types", "") == "rpa":return self.rpaError(aMsg),"n"
            solutionId = aMsg["Summary"].replace(" ","").split("[SolutionID:")[1].split("]")[0].strip()
            masterObj = masterData.query.filter(masterData.solutionId == solutionId,
                                                   masterData.status == "Active",
                                                   masterData.L1Group == aMsg["Assignee"]).first()
            if not masterObj:
                self.workInfo = "单据：%s  solutionId:%s 未从主数据获取到单据处理人信息=>" % (aMsg['Incident ID'],solutionId)
                result = self.modifyAndEmailToServerDesk(aMsg)
                result.append("未知单据");return result,"n"

            #解析出电话、短信所需的信息，后面可以直接使用，如果解析失败，表示单据格式有问题，那么转单给服务台
            smsTelInfo = self.smsTelInfo(aMsg["Summary"],aMsg['Incident ID'], aMsg["Priority"],aMsg["Notes"])
            if smsTelInfo=="failed":
                self.workInfo = "解析单据异常，LMAC无法正确处理，请服务台同事处理=>"
                return self.modifyAndEmailToServerDesk(aMsg),"n"
            callBack ,self.emailAddress = self.getCallRemark(solutionId,masterObj.callRemark,aMsg["Priority"])
            #默认联系主数据中派单组信息
            assignee = masterObj.assignee
            if assignee in ["-",None,"None"] or not assignee:
                assignee = ""
            self.admin = [masterObj.company, masterObj.organization, masterObj.L2Group, assignee, str(masterObj.tel),callBack,masterObj.autoQuickFixHerf]
            if not re.findall("\d",masterObj.actions):
                self.workInfo = "单据：%s  solutionId:%s 没有填写单据的处理流程标识=>" % (aMsg['Incident ID'],solutionId)
                return self.modifyAndEmailToServerDesk(aMsg),"n"
            self.actions = masterObj.actions.split("-") #主数据中定义的该监控点单据的执行步骤
            emailResult = "" #用于判断是否有错误，最后有值表示有错误，否则status=1

            for indexs in range(len(self.actions)):
                if str(self.actions[indexs]) == "6":
                    noticeOwner = self.actions
                    continue
                if self.actions[indexs] == "10":  #rpa单据，变换self.admin
                    j,q,p,num = masterObj.callRemark.split("rpa",1)[1].split("rpaend")[0].split("/")
                    self.admin = [masterObj.company, masterObj.organization, masterObj.L2Group, assignee,num,j,p,q]
                    logging.info(aMsg['Incident ID'] + solutionId + str(self.admin) + str(indexs))
                funs = eval("self.%s" % funAndTag.get(str(self.actions[indexs]))) #初始化标识对应的函数名
                result = funs(aMsg)  #依次执行步骤

                if isinstance(result,list):
                    if "6" in self.actions:  # 比如进入压缩告警，结束前判断是否需要额外通知owner
                        noticeOwner = "y"
                        # self.noticeOwn(aMsg)
                    result.append(self.type)
                    return result,self.actions

                if str(result).find("失败")>=0 or str(result).strip()=="4": #如果函数执行错误，那么记录当前失败的步骤，并且获取接下来需要的操作步骤，邮件发给服务台
                    logging.error(aMsg['Incident ID'] + solutionId + str(self.admin) + funAndTag.get(str(self.actions[indexs]))+"cuowurizhi")
                    if aMsg["Priority"].strip() != "High":
                        actionsDict = {"2": "请转单:%s" % "=>".join(self.admin[:4]),"4": "请发送邮件:%s" % self.emailAddress,"w1":"请发送短信给：%s" % self.admin[4],"w3":"请拨打电话:%s" % self.admin[4]}
                    else:
                        actionsDict = {"0": "请ping 单据中IP，ping通不用电话通知", "1": "请发送短信给：%s" % self.admin[4],
                                        "2": "请转单:%s" % "=>".join(self.admin[:4]), "3": "请拨打电话:%s" % self.admin[4],
                                        "4": "请发送邮件:%s" % self.emailAddress,
                                        "5": "请查询值班表获取转单信息", "6": "", "7": "请从cmdb中获取单据处理信息", "8": "请从dba数据库获取单据处理信息",
                                        "9": "自修复失败", "10": "rpa单据加Q失败，按照文档操作单据，谢谢","11":"请电话通知:%s" % self.admin[4],
                                       "w1":"请发送短信给：%s" % self.admin[4],"w3":"请拨打电话:%s" % self.admin[4]}

                    if self.verResult[0] == "invalid alert through verification":
                        actionsDict = {"2":"请降级转单:%s" % "=>".join(self.admin[:4])}
                    groupObj = serverDesk.query.filter(serverDesk.fouraccounts == aMsg.get("Assignee").strip()).first()
                    if not groupObj:
                        return [self.smsResult[0], self.callResult[0], self.modifyResult[0], self.smsResult[1], self.callResult[1],self.modifyResult[1],"5", self.verResult[0], self.verResult[1]],self.actions
                    self.admin = [groupObj.company,groupObj.org,groupObj.groups,groupObj.assignee]

                    if result.find("失败")>=0: #非邮件的失败，比如转单、电话等
                        nextAction = "\n".join([actionsDict.get(key,"") for key in self.actions[indexs:]])
                        emailResult = self.send_email(aMsg['Incident ID'], aMsg["Priority"], aMsg["Summary"],aMsg["Notes"], result, nextAction,[groupObj.emails.split("/")], "nual", 1)
                        if "6" in self.actions:  # 表示本次不是额外通知失败，并且流程需要额外通知，无论短信、电话、转单失败，都需要额外通知xpo
                            # self.noticeOwn(aMsg)
                            noticeOwner = "y"
                        break

                    #邮件失败，目前只处理存储类型单据，邮件失败，转单给服务台
                    if re.findall(".*4.*2.*",masterObj.actions):#邮件失败，但是单据还在四个账号，那么转给服务台
                        self.workInfo = "==>".join([actionsDict.get(key) for key in self.actions[indexs:]])
                        self.modifyTickets(aMsg)
                        emailResult = "4"      #邮件失败，转单成功，status=4，转单失败status=3-4
                        break

            if not emailResult: #actions中所有步骤没有错误，status="1"
                status = "1"
            elif self.callResult[0] =="n":
                status = ("2-%s" % emailResult).replace("-3","")     #电话失败
            elif self.modifyResult[0] =="n":
                status = ("3-%s" % emailResult).replace("-3","")     #转单失败

            elif self.modifyResult[0] =="y" and str(emailResult)== "4" and self.callResult[0]=="un" and self.smsResult[0]=="un":  # 表示存储，先发邮件失败，转给给服务台成功,否则邮件失败，转单失败，就会进入上一个判断，status=3-4
                status = "4"
            else:
                # 表示无solutonId / 单据格式不对 / 没有获取到单据处理人信息(dba, 主数据) / 程序异常 / rpa单据插入数据库失败 / 触发oc流程失败 / 无值班表号码
                status = ("8-%s" % emailResult).replace("-3","")
            return [self.smsResult[0], self.callResult[0], self.modifyResult[0], self.smsResult[1], self.callResult[1],self.modifyResult[1],status, self.verResult[0], self.verResult[1],self.type],self.actions
        except Exception as e:
            self.workInfo = "%s 请根据单据实际情况操作=>zabbix_switch error:%s :filenum:%s" % (aMsg['Incident ID'],e,e.__traceback__.tb_lineno)
            result = self.modifyAndEmailToServerDesk(aMsg)
            result.append(self.type)
            return result,noticeOwner
