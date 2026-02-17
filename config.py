import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # WITHOUT THIS, LOGIN WILL NOT WORK
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-123'
    
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    #     'sqlite:///' + os.path.join(basedir, 'instance', 'rxinsight.db')

    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:root@localhost:3307/rxinsight"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

