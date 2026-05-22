pipeline {
    agent any

    parameters {
        string(name: 'CASE_ID', defaultValue: '', description: '禅道用例ID（多个用逗号分隔）')
        string(name: 'OUTPUT_XML', defaultValue: '', description: 'output.xml文件路径（留空则从工作空间读取）')
    }

    environment {
        ZENTAO_URL  = 'https://zt.hzbox.net'
        ZENTAO_USER = 'xuwenjun'
        // 密码通过Jenkins凭据管理，不要明文写在这里
        ZENTAO_PWD  = credentials('zentao-password')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                sh 'pip3 install robotframework pyserial paramiko pyyaml requests 2>/dev/null || pip install robotframework pyserial paramiko pyyaml requests'
            }
        }

        stage('Parse Results & Sync Zentao') {
            steps {
                script {
                    def xmlPath = params.OUTPUT_XML ?: 'results/output.xml'
                    def caseId = params.CASE_ID

                    if (!caseId) {
                        error '请提供禅道用例ID参数（CASE_ID）'
                    }

                    if (!fileExists(xmlPath)) {
                        error "output.xml文件不存在: ${xmlPath}，请先在本地运行测试并上传结果"
                    }

                    sh """
                        python3 libraries/zentao_sync.py \
                            --xml ${xmlPath} \
                            --url ${ZENTAO_URL} \
                            --user ${ZENTAO_USER} \
                            --pwd ${ZENTAO_PWD} \
                            --case-id ${caseId}
                    """
                }
            }
        }
    }

    post {
        success {
            echo '禅道同步完成'
        }
        failure {
            echo '禅道同步失败，请检查日志'
        }
    }
}
