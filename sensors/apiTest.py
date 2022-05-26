from flask import Flask
from flask_restful import Api, Resource, reqparse
from werkzeug.datastructures import FileStorage

app = Flask(__name__)
api = Api(app)


class Upload(Resource):
  def post(self,id):
    parser = reqparse.RequestParser()
    parser.add_argument('filee', type=FileStorage, location='files')   #文件和图片类型，从werkzeug.datastructures导包
    args = parser.parse_args()

    # file = args['file']  #或者args.get("file")
    file = args.get("filee")
    file.save("123.png")  #文件本身save方法保存上传的文件，文件名随意取
    return 'uploadFile %s success' % id


  def delete(self,id):
    pass
api.add_resource(Upload, '/upload/<id>')


if __name__ == '__main__':
  app.run("0.0.0.0:82")