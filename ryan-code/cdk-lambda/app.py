from aws_cdk import App
from ecr_lambda_stack import EcrLambdaStack

app = App()
EcrLambdaStack(app, "EcrLambdaStack")
app.synth()