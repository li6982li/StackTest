
from st2common.runners.base_action import Action

class Ticket(Action):
    def run(self,monitorTicket):
        try:
            print(monitorTicket)
            print(type(monitorTicket))
            # if isinstance(monitorTicket,str):
            #     monitorTicket = eval(monitorTicket)
            #
            # if monitorTicket['Priority'] == "Critical":
            #     if monitorTicket['Submitter'] in ['niulx2', 'tiandj1', 'chenlei16', 'shihy4', 'huangjie5', 'wahmad']:
            #         return ""
            #     return "P1"
            # if monitorTicket.get('Reported Source') == "Monitor" and \
            #         (monitorTicket.get("Assignee") in ["automation_i", "automation_a", "automation_b", "automation_p"] or
            #          (monitorTicket.get("Assigned Group") == "Automation" and monitorTicket.get(
            #              'Assigned Organization') == "CC-Monitoring" and monitorTicket.get("Assignee") == "auto_fix"
            #          )):
            #     return "auto"
            # else:
            #     return ""
        except Exception as e:
            print("error:%s" % e)
            return e