pipeline {
    agent any

    environment {
        REGISTRY = 'your-registry:5000'  // 改成你的镜像仓库地址
        IMAGE_PREFIX = 'dev-metric'
        VERSION = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git submodule update --init --recursive || true'
            }
        }

        stage('Build Go Backend') {
            steps {
                sh "docker build -f Dockerfile.go -t ${IMAGE_PREFIX}/backend:${VERSION} -t ${IMAGE_PREFIX}/backend:latest ."
            }
        }

        stage('Build Python AI') {
            steps {
                sh "docker build -f Dockerfile.ai -t ${IMAGE_PREFIX}/ai:${VERSION} -t ${IMAGE_PREFIX}/ai:latest ."
            }
        }

        stage('Build Intent Model') {
            steps {
                sh "docker build -f Dockerfile.model -t ${IMAGE_PREFIX}/intent:${VERSION} -t ${IMAGE_PREFIX}/intent:latest ."
            }
        }

        stage('Build Frontend') {
            steps {
                sh "docker build -f Dockerfile.web -t ${IMAGE_PREFIX}/web:${VERSION} -t ${IMAGE_PREFIX}/web:latest ."
            }
        }

        stage('Push Images') {
            steps {
                sh """
                    docker push ${REGISTRY}/${IMAGE_PREFIX}/backend:${VERSION}
                    docker push ${REGISTRY}/${IMAGE_PREFIX}/backend:latest
                    docker push ${REGISTRY}/${IMAGE_PREFIX}/ai:${VERSION}
                    docker push ${REGISTRY}/${IMAGE_PREFIX}/ai:latest
                    docker push ${REGISTRY}/${IMAGE_PREFIX}/intent:${VERSION}
                    docker push ${REGISTRY}/${IMAGE_PREFIX}/intent:latest
                    docker push ${REGISTRY}/${IMAGE_PREFIX}/web:${VERSION}
                    docker push ${REGISTRY}/${IMAGE_PREFIX}/web:latest
                """
            }
        }

        stage('Deploy') {
            steps {
                sh """
                    ssh deploy@your-server 'cd /opt/dev-metric && \
                        docker compose pull && \
                        docker compose up -d --remove-orphans && \
                        docker compose ps'
                """
            }
        }
    }

    post {
        success {
            echo "Deploy SUCCESS: version=${VERSION}"
        }
        failure {
            echo "Deploy FAILED"
        }
        always {
            sh 'docker image prune -f'
        }
    }
}
