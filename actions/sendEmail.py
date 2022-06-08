

from st2common.runners.base_action import Action

from exchangelib import DELEGATE, Configuration
from exchangelib import Account, Credentials, Message
from exchangelib import Body


class Mails(Action):
    def run(self, incident, priority, summary, notes, validationResults,
                    toRecipients,ccRecipients,nextAction,types,
                    userName,pwd,primarySmtpAddress,url):
        print(123345654423423423423)
        if toRecipients:
            to_recipients = toRecipients.split("/")
        else:to_recipients = ""

        if ccRecipients:
            cc_recipients = ccRecipients.split("/")

        else:
            cc_recipients = ""
        try:
            cred = Credentials(userName, pwd)
            config = Configuration(server='mail.lenovo.com', credentials=cred)
            account = Account(
                primary_smtp_address=primarySmtpAddress,
                config=config,
                autodiscover=False,
                access_type=DELEGATE,
            )
        except Exception as e:
            print(12345,e.__traceback__.tb_lineno)
            return "Connected Fail"

        try:
            if types == "nual":
                actions = nextAction.split("|_|")
                n_action = "\n".join(actions)
                subject = "[AutoMonitoring] ==> Incident" + " " + incident + "需要监控服务台关注和处理"
                content_body = "%s?u=/servlet/ViewFormServlet?form=Lenovo_INC_OpenTicketByURL&server=lenovoargroup&F1000000161=%s" % (url,incident) + "\n" +\
                           "Priority: %s" % priority + "\n" + "Summary: %s" % summary + "\n" + "Notes: %s" % notes + "\n" + \
                           "Automated verification results: %s" % validationResults + "\n" + "Next Action: "  + "\n" +n_action + "\n" + "\n" + "****************************" + "\n" +"Email send by automation" + "\n" + "****************************"
                content_body = Body(content_body)

            elif types =="notice":
                subject = "[AutoMonitoring]通知IP管理员结果！"
                content_body = validationResults +"\n" + nextAction+ "\n" + notes + "\n" + "单据号:%s" % incident + "\n" + "级别:%s" % priority \
                + "\n" + "描述:%s" % summary
                content_body = Body(content_body)

            elif types =="quick":
                ip = summary.split("|_|")[-1].split(":")[-1]
                action, roleId = nextAction.split("role")
                content_body = "******************** Auto Quick Fix Link/自修复工具地址 ********************" + "</br>" * 3 +"</br>" + "incident:%s" % incident + "</br>" + "priority:%s" % priority + "</br>" + "summary:%s" % summary
                subject = "[Monitoring Ticket Auto Quick Fix]=================>[%s]" % incident
                content_body = Body(content_body)

            elif types == "Storage":
                subject = " [New Cloud Storage] ==> Incident" + " " + incident + "需要XPO关注和处理的存储单据"
                content_body = "Priority: %s" % priority + "\n" + "Summary: %s" % summary + "\n" + "Notes: %s" % notes + "\n" + \
                               "\n" + "\n" + "****************************" + "\n" + "Email send by automation" + "\n" + "****************************"
                content_body = Body(content_body)

            elif types == "filesystem":
                subject = "[Filesystem alarm] ==> Incident" + incident + "需要XPO关注和协助处理的文件系统单据"
                content_body = "%s?u=/servlet/ViewFormServlet?form=Lenovo_INC_OpenTicketByURL&server=lenovoargroup&F1000000161=%s" % (url,incident) + "\n" + "Priority: %s" % priority + "\n" + "Summary: %s" % summary + "\n" + "Notes: %s" % notes + "\n" + \
                               "\n" +nextAction + "\n"+ "从cmdb中获取的owner信息如下:" + "\n" +"cmdbOwner:%s" %validationResults["cmdbOwner"]\
                               + "\n" + "cmdbPhone:%s" %validationResults["cmdbPhone"]+ "\n" +"Please inform server app owner of this ticket" + "\n" + "****************************" + "\n" + "Email send by automation" + "\n" + "****************************"
                content_body = Body(content_body)

            else:
                content_body="以下单据没有电话通知到二线，请通知二线" + "\n" +types + "\n" +validationResults + "\n" +nextAction + "\n" + "\n" + "****************************" + "\n" +"Email send by automation" + "\n" + "****************************"
                subject = "[AutoMonitoring] ==> Incident" + " " + incident + "需要监控服务台电话通知二线"
                content_body = Body(content_body)

            try:
                m = Message(account=account, subject=subject, body=content_body,
                            to_recipients=to_recipients,
                            cc_recipients=cc_recipients)
                m.send()
            except Exception as e:
                return ["n",str(e)]
            return ["y","y"]
        except Exception as e:
            print(6789,e.__traceback__.tb_lineno)

