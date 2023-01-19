# Importing flask module in the project is mandatory
# An object of Flask class is our WSGI application.
from flask import Flask, request,url_for, Response
import os
import dotenv
import requests
from bigcommerce.api import BigcommerceApi


# Flask constructor takes the name of
# current module (__name__) as argument.
app = Flask(__name__)

# Look for a .env file
if os.path.exists('.env'):
    dotenv.load_dotenv('.env')

# Load configuration from environment, with defaults
app.config['APP_URL'] = os.getenv('APP_URL', 'http://localhost:5000')  # must be https to avoid browser issues
app.config['APP_CLIENT_ID'] = os.getenv('APP_CLIENT_ID')
app.config['APP_CLIENT_SECRET'] = os.getenv('APP_CLIENT_SECRET')
app.config['TAX_PROVIDER_ID'] = os.getenv('TAX_PROVIDER_ID')
app.config['PROVIDER_USERNAME'] = os.getenv('PROVIDER_USERNAME')
app.config['PROVIDER_PASSWORD'] = os.getenv('PROVIDER_PASSWORD')



#
# Error handling and helpers
#
def error_info(e):
    content = ""
    try:  # it's probably a HttpException, if you're using the bigcommerce client
        content += str(e.headers) + "<br>" + str(e.content) + "<br>"
        req = e.response.request
        content += "<br>Request:<br>" + req.url + "<br>" + str(req.headers) + "<br>" + str(req.body)
    except AttributeError as e:  # not a HttpException
        content += "<br><br> (This page threw an exception: {})".format(str(e))
    return content


@app.errorhandler(500)
def internal_server_error(e):
    content = "Internal Server Error: " + str(e) + "<br>"
    content += error_info(e)
    return content, 500


@app.errorhandler(400)
def bad_request(e):
    content = "Bad Request: " + str(e) + "<br>"
    content += error_info(e)
    return content, 400


def jwt_error(e):
    print(f"JWT verification failed: {e}")
    return "Payload verification failed!", 401


def client_id():
    return app.config['APP_CLIENT_ID']

def client_secret():
    return app.config['APP_CLIENT_SECRET']

def tax_provider_id():
    return app.config['TAX_PROVIDER_ID']

#
# Update the connection API
# 
# This functions helps to make the connection update from tax provider to BC
# returns the api result text  
def update_the_connection(store_hash,access_token):
    url = f"https://api.bigcommerce.com/stores/{store_hash}/v3/tax/providers/{tax_provider_id()}/connection"

    payload = {
        "username": app.config['PROVIDER_USERNAME'],
        "password": app.config['PROVIDER_PASSWORD']
    }
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": access_token
    }

    response = requests.request("PUT", url, json=payload, headers=headers)

    return response.text



#
# OAuth pages
#

# The Auth Callback URL. See https://developer.bigcommerce.com/api/callback
@app.route('/api/auth')
def auth_callback():
    print('This route is auth_callback')
    # Put together params for token request
    code = request.args['code']
    context = request.args['context']
    scope = request.args['scope']
    store_hash = context.split('/')[1]
    redirect = app.config['APP_URL'] + url_for('auth_callback')

    # Fetch a permanent oauth token. This will throw an exception on error,
    # which will get caught by our error handler above.
    client = BigcommerceApi(client_id=client_id(), store_hash=store_hash)
    token = client.oauth_fetch_token(client_secret(), code, context, scope, redirect)
    
    access_token = token['access_token']

    # now we have the store_token and store_hash
    # so we can just need to update the connection
    updateData = update_the_connection(store_hash,access_token)

    # Log user in and redirect to app home
    # TODO replace the return value with render, if you need more beautifull frontend
    return updateData


# The Load URL. See https://developer.bigcommerce.com/api/load
@app.route('/api/load')
def load():
    print('This route is load')
    # Decode and verify payload
    payload = request.args['signed_payload_jwt']
    try:
        user_data = BigcommerceApi.oauth_verify_payload_jwt(payload, client_secret(), client_id())
    except Exception as e:
        return jwt_error(e)

    bc_user_id = user_data['user']['id']
    email = user_data['user']['email']
    store_hash = user_data['sub'].split('stores/')[1]

    # Log user in and redirect to app interface
    # TODO replace the return value with render, if you need more beautifull frontend
    return f'The current user is {email} with user id {bc_user_id} and the store hash is {store_hash} <br><h1>Please Reinstall this app to update the connection if required</h1>'


# The Uninstall URL. See https://developer.bigcommerce.com/api/load
@app.route('/api/uninstall')
def uninstall():
    print('This route is uninstall')
    # This route to have signed_payload_jwt in its request args
    # So you can Decode and verify payload just like the load route is doing,
    # I'm not using this here for the time being as it is not a necessity
    return Response('Deleted', status=204)


# The route() function of the Flask class is a decorator,
# which tells the application which URL should call
# the associated function.
@app.route('/')
# ‘/’ URL is bound with hello_world() function.
def hello_world():
	return 'Hello World'

# main driver function
if __name__ == '__main__':

	# run() method of Flask class runs the application
	# on the local development server.
	app.run()
