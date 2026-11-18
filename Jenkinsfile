
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
                    pip3 install -r requirements.txt
                    pip3 install flake8
                '''
            }
        }

        stage('Lint') {
            steps {
                sh 'flake8 . --max-line-length=120'
            }
        }

        stage('Application Import Check') {
            steps {
                sh 'python3 -c "import app"'
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
