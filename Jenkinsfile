
pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    python3 -m venv .venv
                    .venv/bin/pip install -r requirements.txt
                    .venv/bin/pip install flake8
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '.venv/bin/flake8 --exclude=.venv --max-line-length=120 .'
            }
        }

        stage('Application Import Check') {
            steps {
                sh '.venv/bin/python -c "import app"'
            }
        }

        stage('Deploy') {
            steps {
                sshagent(['filesafe-ssh']) {
                    sh '''
                        ssh ubuntu@172.31.2.146 \
                        "cd ~/FileSafe && git pull origin main"
                    '''
                }
            }
        }

        stage('Build and Restart') {
            steps {
                sshagent(['filesafe-ssh']) {
                    sh '''
                        ssh ubuntu@172.31.2.146 \
                        "cd ~/FileSafe && docker compose up -d --build"
                    '''
                }
            }
        }
    }
}
