import time
import datetime

class Duty():

    def getDuty(self,dutyList,types, mon_day, hour_min):
        for data in dutyList:
            data = eval(data)
            duty_mon_day = data.get(type)
            if duty_mon_day:
                value = duty_mon_day.get(mon_day)
                if value:
                    # 变量当天的值班信息，跟上面的时间相匹配
                    for min, tel in value.items():
                        beg_time, end_time = min.split("-")
                        # 表示10:00-18:00这样，没有过24:00的值班表
                        if end_time > beg_time:
                            # 告警时间，大于开始，小于结束，表示匹配正确
                            if houre_min >= beg_time and houre_min < end_time:
                                return tel
                        else:
                            # 20：00-06:00 表示值班时间垮24:00，需要把值班时间拆成20:00-24:00 & 00:00-06:00可以比较的两部分
                            if (houre_min >= beg_time and houre_min < "24:00") or (
                                    houre_min >= "00:00" and houre_min < end_time):
                                return tel

    def run(self, ticketInfo,mappingList,dutyList,noticeInfo):
        try:
            noticeInfo = eval(noticeInfo)
            times = time.strftime("%m-%d %H:%M", time.localtime(int(time.time())))
            mon_day, hour_mins = str(times).split(" ")
            """            
            注意，如果没有跨晚上00；00，那么mapping.txt中telAdmin[1]一定要填""
            """
            # 获取到mapping文件存放的值班类型以及对应分段时间点
            for data in mappingList:
                data = eval(data)
                data = data.get(ticketInfo["Assignee"])
                if data:
                    telAdmin = data.get(ticketInfo["Summary"].split("[Solution ID:")[1].split("]")[0].strip())
                    if telAdmin:break
                    return "ticketInfo['Incident ID'] unfind duty table"
            dutyTime = telAdmin[1]  # 分段时间点
            types = telAdmin[0]
            if isinstance(dutyTime, dict) == True:  # 表示ludp值班类型
                note = eval(ticketInfo["Notes"])  # ludp的note是个字典
                itcode = note.get("it_code")  # 获取itcode
                if itcode in ["group", "NONE", "None"] or not itcode:
                    itcode = ""
                dutyTime = dutyTime.get(note.get("Support_Group_name", "Support_Group_name"))  # ludp类型的分段时间点
                if not dutyTime:  # 不是BI和operation值班表，直接拨打note里面的电话
                    noticeInfo.update({"itcode":itcode,"phone":note.get("telephone")})
                    return noticeInfo
                dutyTime = dutyTime[0]  # 得到最终分段时间点
                types = note.get("Support_Group_name")
            if dutyTime > hour_mins >= "00:00":  # 判断是否需要日期减一天
                mon_day = str(datetime.date.today() - datetime.timedelta(days=1)).split("-", 1)[-1]
            org = self.getDuty(dutyList,types, mon_day, hour_mins)
            # 没有匹配到值班号码
            if len(org) == 9:
                self.workInfo = "未找到值班号码，请服务台同事查询并通知用户=>"
                return self.modifyAndEmailToServerDesk(ticketInfo)
            # 正常值班表
            elif len(org) == 6:
                self.admin = org
                return "success"
            else:
                # 表示ludp值班表
                self.admin = [note.get("Support_Company"), note.get("Support_Organization"), note.get("Support_Group_name"),
                              itcode] + org
                return "success"
        except Exception as e:
            self.workInfo = "获取值班表时，发生异常，请服务台同事处理=>duty fun error:%s:filenum:%s" % (e, e.__traceback__.tb_lineno)
            return self.modifyAndEmailToServerDesk(ticketInfo)
        finally:
            logging.info(ticketInfo['Incident ID'] + "值班表" + str(self.admin))
