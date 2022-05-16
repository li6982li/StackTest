import json
import logging
import time,datetime
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.profile import region_provider
from aliyunsdkdyvmsapi.request.v20170525 import SingleCallByTtsRequest
import configparser

from st2common.runners.base_action import Action
#
class SmsTtsCall(object):
    """
    文本转语音外呼
    """
    def __init__(self,types,REGION,PRODUCT_NAME,DOMAIN,ACCESS_KEY_ID,
                 ACCESS_KEY_SECRET,template):
        if not template:
            template = {
                "TTS_CODE_LMAC":"TTS_213690369,TTS_213675383,TTS_213690368,TTS_213770311,TTS_213740318,TTS_213740317,TTS_213675319,TTS_213770299,TTS_213546221,TTS_213541230,TTS_213541078",
                "TTS_CODE_COMPRESS":"TTS_205811280,TTS_205811282,TTS_205816155,TTS_205826028,TTS_205816091",
                "TTS_CODE_STANDARD":"TTS_232176936,TTS_232172003,TTS_232167027,TTS_232176950",
                "LMAC":"Incident",
                "STANDARD":"Incident",
                "COMPRESS":"PhoneNumber",
            }
        else:
            template.update(template)
        self.REGION = REGION
        self.PRODUCT_NAME =PRODUCT_NAME
        self.DOMAIN = DOMAIN
        self.ACCESS_KEY_ID = ACCESS_KEY_ID
        self.ACCESS_KEY_SECRET =ACCESS_KEY_SECRET
        self.ALI_SMS_SIGN = ""
        self.CALLED_SHOW_NUMBER = ""
        self.TTS_CODE = template.get("TTS_CODE_%s" % types).split(",")
        self.param = template.get(types)
        print(self.TTS_CODE)

    def callVoice(self, phoneNum, ttsCode, ttsParam=None):

        # 初始化AcsClient
        acsClient = AcsClient(self.ACCESS_KEY_ID, self.ACCESS_KEY_SECRET, self.REGION)
        region_provider.add_endpoint(self.PRODUCT_NAME, self.REGION,self.DOMAIN)
        __business_id = str(int(time.time())) + phoneNum
        ttsRequest = SingleCallByTtsRequest.SingleCallByTtsRequest()
        # 申请的语音通知tts模板编码,必填
        ttsRequest.set_TtsCode(ttsCode)
        # 设置业务请求流水号，必填。后端服务基于此标识区分是否重复请求的判断
        ttsRequest.set_OutId(__business_id)
        # 语音通知的被叫号码，必填。
        ttsRequest.set_CalledNumber(phoneNum)
        # 语音通知显示号码，必填。
        ttsRequest.set_CalledShowNumber("")
        # tts模板变量参数
        if ttsParam:
            ttsRequest.set_TtsParam(ttsParam)
        # 调用tts文本呼叫接口，返回json
        ttsResponse = acsClient.do_action_with_exception(ttsRequest)
        ttsResponse = str(ttsResponse, encoding='utf-8')
        return ttsResponse






class VoiceCallFlow(SmsTtsCall):
    def aliCall(self, phoneNum, ttsCode, ttsParams):
        try:
            response = self.callVoice(phoneNum, ttsCode, ttsParams)
            print("call result logging %s" % response)
            return response
        except Exception as e:
            result = "phone:%s Voice notification sending abnormally:%s" % (phoneNum,e)
            print(result)
            return result


    def voiceTemplateParameters(self,host, priority):
        """
        Parameter format required to generate Alibaba Cloud voice template
        """
        host= host.replace(".", "。")
        priority = priority.replace(".", "。")

        tts_params = {"AlertContent": host, self.param: priority}
        return tts_params

    def sendVoices(self, phoneNum, voiceMsg1,voiceMsg2):
        try:
            print(phoneNum, voiceMsg1,voiceMsg2)
            times = datetime.datetime.now()
            ttsCode = self.TTS_CODE[0]
            #参数处理
            ttsParams = self.voiceTemplateParameters(voiceMsg1,voiceMsg2)
            #返回是否正确拨打码，拨打时间
            callResult= self.aliCall(phoneNum, ttsCode, ttsParams)
            try:
                callResult = json.loads(callResult)
            except:
                #表示电话未拨打
                return ["号码未拨打...", callResult,0,times,"500"]

            # 当'CallId'这个key在打电话返回的字典call_result中,说明打电话正常,否则就时打电话异常
            if not callResult.get("CallId"):
                # 在'CallId' 不在打电话返回的列表中的情况下,如果code == "isv.BUSINESS_LIMIT_CONTROL" 说明该手机号码触发该模板的业务级流控,需要切换模板;
                # 阿里云语音电话模板的业务级流控: 同一个手机号使用同一个模板24小时内最多打50次电话,一分钟2次,
                code = callResult['Code']
                if code == "isv.BUSINESS_LIMIT_CONTROL":
                    i = 0
                    tts_code_len = len(self.TTS_CODE) - 1
                    while i < tts_code_len:
                        i = i + 1
                        ttsCode = self.TTS_CODE[i]
                        # 执行打电话
                        callResult = self.aliCall(phoneNum, ttsCode, ttsParams)
                        callResult = json.loads(callResult)
                        code = callResult['Code']
                        # 当'CallId'这个key在打电话返回的字典call_result中,说明打电话正常,
                        # 如果'CallId'存在and code != "isv.BUSINESS_LIMIT_CONTROL",说明打电话正常;
                        if callResult.get('CallId') and code != "isv.BUSINESS_LIMIT_CONTROL":
                            break

            if callResult.get('CallId'):
                call_id = callResult['CallId']
                result = "拨打成功...."

            elif callResult.get('Code') == "isv.BUSINESS_LIMIT_CONTROL":
                result = "号码占线...."

            else:

                result = "code:%s--" % callResult.get("Code")
            return [result ,callResult]

        except Exception as e:
            print("sendVoices error:%s" % e)
            return [e,e.__traceback__.tb_lineno]



class Voices(Action):
    def run(self,phoneNum,voiceMsg1, voiceMsg2,types,REGION,PRODUCT_NAME,DOMAIN,ACCESS_KEY_ID,ACCESS_KEY_SECRET,template):
        """

        :param phoneNum:
        :param voiceMsg1:
        :param voiceMsg2:
        :param types:
        :param REGION:
        :param PRODUCT_NAME:
        :param DOMAIN:
        :param ACCESS_KEY_ID:
        :param ACCESS_KEY_SECRET:
        :param template:
        :return:
        """
        obj = VoiceCallFlow(types,REGION,PRODUCT_NAME,DOMAIN,ACCESS_KEY_ID,ACCESS_KEY_SECRET,template)
        r = obj.sendVoices(phoneNum,voiceMsg1,voiceMsg2)
        print(666,r)
        return r




