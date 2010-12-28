import datetime
import os.path
from fabric.api import *

env.project_name = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
env.user_name = env.project_name
env.production = False
env.server_flavor = None


# ENVIRONMENTS

def staging():
    """Deploy on staging server"""
    env.user_name = 'pb'
    env.hosts = ['%(user_name)s@web01.pb.io' % env]
    env.path = '/home/%(user_name)s/projects/%(project_name)s' % env
    env.server_flavor = 'mod_wsgi'

def production():
    """Deploy on live server"""
    env.production = True
    raise NotImplementedError, "production environment not set up yet."


# COMMANDS

def deploy_only():
    """Push (local) and pull (remote) the Github repo"""
    local("git push origin master" % env)
    with cd(env.path):
        run("git pull origin master" % env)

def deploy():
    """Update code, migrate database and restart server."""
    if env.production:
        input = prompt('Are you sure you want to deploy to the production server?', default="n", validate=r'^[yYnN]$')
        if input not in ['y','Y']:
            exit()
    deploy_only()
    migrate()
    reload_server()

def migrate():
    """Sync and migrate the database."""
    with cd(env.path):
        run("../../.virtualenvs/%(project_name)s/bin/python ./manage.py syncdb" % env)
        run("../../.virtualenvs/%(project_name)s/bin/python ./manage.py migrate" % env)

def reload_server():
    """Reload the webserver and take the server flavor into account."""
    if env.server_flavor == 'lighttpd':
        run('~/init/%(project_name)s restart' % env)
    elif env.server_flavor == 'mod_wsgi':
        run("touch %(path)s/deploy/project.wsgi" % env)
    elif env.server_flavor == 'gunicorn':
        run("sudo supervisorctl restart %(user_name)s__%(project_name)s" % env)
    else:
        raise NotImplementedError, "reload_server() is not configured for %(server_flavor)s server flavor." % env

def setup_server():
    """Setup the staging server"""
    if env.production:
        raise NotImplementedError, "server setup is only possible on staging servers"
    with cd('projects'):
        run('git clone git@github.com:philippbosch/%(project_name)s.git %(project_name)s' % env)
        run('virtualenv --no-site-packages ~/.virtualenvs/%(project_name)s' % env)
        run('~/.virtualenvs/%(project_name)s/bin/easy_install pip' % env)
        with cd(env['project_name']):
            run('~/.virtualenvs/%(project_name)s/bin/pip install -r requirements.txt' % env)
            run('/opt/pbadmin/create_mysql_db.py %(user_name)s %(project_name)s %(project_name)s_test' % env)
            run('echo "DATABASES[\'default\'][\'NAME\']=\'%(user_name)s_%(project_name)s\'" > settings_local.py' % env)
            run('echo "DATABASES[\'default\'][\'USER\']=\'%(user_name)s_%(project_name)s\'" >> settings_local.py' % env)
            run('echo "DATABASES[\'default\'][\'PASSWORD\']=\'%(project_name)s_test\'" >> settings_local.py' % env)
            run('~/.virtualenvs/%(project_name)s/bin/python manage.py syncdb --noinput' % env)
            run('~/.virtualenvs/%(project_name)s/bin/python manage.py createsuperuser --username=pb --email=hello@pb.io --noinput' % env)
            run('echo "from django.contrib.auth.models import User ; u = User.objects.get(username=\'pb\') ; u.set_password(\'pb\') ; u.save()" | ~/.virtualenvs/%(project_name)s/bin/python manage.py shell' % env)
            run('~/.virtualenvs/%(project_name)s/bin/python manage.py migrate' % env)
    with cd('conf'):
        run('/opt/pbadmin/create_apache_conf.py %(project_name)s %(project_name)s.test.pb.io' % env)
    sudo('ln -s ~/conf/%(project_name)s.apache.conf /etc/apache2/sites-available/%(user_name)s.%(project_name)s-test' % env)
    sudo('a2ensite %(user_name)s.%(project_name)s-test' % env)
    sudo('/etc/init.d/apache2 reload')

def drop_server():
    """Drop the staging server"""
    if env.production:
        raise NotImplementedError, "server dropping is only possible on staging servers"
    input = prompt('Do you really want to drop the server?', default="n", validate=r'^[yYnN]$')
    if input not in ['y','Y']:
        exit()
    
    with cd('projects'):
        run('rm -rf %(project_name)s' % env)
    run('rm -rf ~/.virtualenvs/%(project_name)s' % env)
    run('rm -f conf/%(project_name)s.apache.conf' % env)
    sudo('a2dissite %(user_name)s.%(project_name)s-test' % env)
    sudo('rm -f /etc/apache2/sites-available/%(user_name)s.%(project_name)s-test' % env)
    run('echo DROP USER "%(user_name)s_%(project_name)s@localhost" | mysql' % env)
    run('echo DROP DATABASE %(user_name)s_%(project_name)s | mysql' % env)
    sudo('/etc/init.d/apache2 reload')

def get_dump():
    """Create, download and import database dump"""
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    env.dump_filename = "dump-%s.sql" % timestamp
    with cd(env.path):
        run('export DJANGO_SETTINGS_MODULE=settings ; echo "from django.conf import settings ; print \'mysqldump -u%%(USER)s -p%%(PASSWORD)s %%(NAME)s > %(dump_filename)s\' %% settings.DATABASES[\'default\']" | ~/.virtualenvs/%(project_name)s/bin/python | sh' % env)
        get('%(path)s/%(dump_filename)s' % env, env.dump_filename)
        run('rm -f %(path)s/%(dump_filename)s' % env)
    if prompt('Import dump and OVERWRITE EXISTING DATABASE? (y/n)', default="n") == "y":
        local('python ./manage.py dbshell < %(dump_filename)s' % env)
        if prompt('Delete downloaded dump? (y/n)', default="n") == "y":
            local('rm %(dump_filename)s' % env)
