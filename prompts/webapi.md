
# flyte web api

Create a web api for Flyte rendering using FastAPI. 

The API allows a POST of form or json formatted data that specifies a URL
to a web page, or a GET with the URL encoded in a query. There is one endpoint
for rendering to PNG, and another for rendering to PDF.  The render returns PNG
for display and PDF for download. 

The API also presents a form where your can enter the URL. 

Endpoints:

* `/` Displays a form where user can enter a URL, and instructions for the pther interfaces
* `png`: POST with JSON or form data with a URL, or GET with the query `url=` to render to png for display. 
* `pdf`: Similar to `png` but render to pdf for download

## Docker

Also create a directory, `/docker` that has a Dockerfile and docker-compose file
for starting a docker server. Set the Daddy label to `webr.jtlapp.net`

