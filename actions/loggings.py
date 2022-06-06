from st2common.runners.base_action import Action


class Test(Action):


    def run(self,a,b,c):
        self.logger.info(str(a))
        self.logger.info(str(b))
        self.logger.info(str(c))



