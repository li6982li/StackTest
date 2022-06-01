"""
Filename:           delMysqlConnect.py
Description:        Native statement connection processing mysql
Create Date:        2020/12/06 09:00:00
Author:             yannan li
Email:              liyn25@lenovo.com
Team Members:       Bruce Mao, Jinhui Ma, Yannan Li
Version:            1.0
Change History      Date                    Modified by                 Modified Reason
CH3                 12/23/2020              Yannan Li                Code optimization

"""
import time
import pymysql
pymysql.install_as_MySQLdb()
from st2common.runners.base_action import Action

class mysqlDb(object):

    # 连接数据库
    def conndb(self,host,user,password,db):
        try:
            db = pymysql.connect(host, user, password, db)
            return db
        except Exception as e:
            print(66,e)
            return "connect mysql failed %s" % str(e)



    # 获取数据#     @reconnectdb
    def fechdb(self, host,user,password,db,solutionId,assignee):
        db = self.conndb(host,user,password,db)
        try:
            t = time.time()
            cursor = db.cursor()
            cursor.execute("select * from request_data where solutionId='%s' and L1Group='%s' and status='Active'"%(solutionId,assignee))
            results = cursor.fetchall()
            cursor.close()
            return results
        except Exception as e:
            db.rollback()
            return "get values failed %s" % str(e)

        finally:
            print("guanb ")
            db.close()



class ParseInfo(mysqlDb):

    def parseTicket(self,summary,notes,incident,priority):
        try:
            smsIp = ""
            try:
                hostName, ip = summary.split("|_|")[-1].strip().split(':')  # 设备
                smsInfo = summary.split("Alert]")[-1].split("|_|")[0]
            except Exception as e:
                hostName, ip = "未知", "未知"
                smsInfo = summary.split("Alert]")[-1]
            if "Solarwinds Alert" in summary:
                ip, hostName = summary.split("|_|")[-1].strip().split(':')  # 网络
                smsHostName = "的网络设备:%s, " % hostName
                smsIp = "IP:%s" % ip
                callIp = "IP地址为:%s的网络设备" % ip
                type = "network"

            elif notes.find("AppSystem:") >= 0:  # 统一的应用监控
                types = notes.split("AppSystem:")[1].split("]")[0]
                smsHostName = "的%s应用监控点" % types
                callIp = "%s应用监控点" % ".".join(types.replace("-", ""))
                type = types

            elif "Splunk Alert" in summary:
                smsHostName = "splunk"
                callIp = "s.p.l.u.n.k"
                type = "splunk"

            elif "New Storage Alert" in summary:
                smsHostName = "的存储设备"
                callIp = "存储设备"
                type = "stroage"

            elif "Solman Alert" in summary:
                smsHostName = "solman"
                callIp = "应用监控"
                type = "solman"

            elif "XClarity Alert" in summary:
                ip = summary.split("|_|")[-2].split("_")[-1]
                smsHostName = "的设备SN号：%s " % ip
                callIp = "SN号为:%s的设备" % ip
                type = "hardware"

            elif "Support_Organization" in notes and "job_name" in notes:  # ludp & 麦哲伦单据
                notes = eval(notes)
                types = notes.get("system_name", "ludp")
                smsHostName = "%s应用监控点，Job Name:%s" % (types, notes.get("job_name"))
                callIp = "%s应用监控点" % types.replace("ludp", "L.U.D.P")
                type = types
            else:
                smsHostName = "的设备：%s, " % hostName
                smsIp = "IP:%s" % ip
                callIp = "IP地址为:%s的设备" % ip
            priToP = {"High": "P2", "Medium": "P3", "Low": "P4"}
            callIncident = "后四位：%s,发生%s级别的告警" % ("".join(incident)[-4:], priToP.get(priority))
            return [smsHostName,smsIp,smsInfo,callIp,callIncident]
        except Exception as e:
            print(e,e.__traceback__.tb_lineno)
            return "Failed"


class ParseAction(Action):
    def run(self,host,user,password,db,tickets):
        dbObj = ParseInfo()
        tickets = eval(tickets)
        solutionId = tickets["Summary"].split("[Solution ID:")[1].split("]")[0].strip()
        assignee= tickets["Assignee"]
        master = dbObj.fechdb(host,user,password,db,solutionId,assignee)

        print("主数据",master)
        if isinstance(master,tuple) and str(master).find("0")>=0:
            return dbObj.parseTicket(tickets["Summary"],tickets["Notes"],tickets["Incident ID"],tickets["Priority"])



