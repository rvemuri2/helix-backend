# How to Run the App

1. have python3 installed as pre-req. Clone this repo 

2. enter the folder in a code editor, run python3 -m venv venv

3. run source venv/bin/activate

4. run pip install -r requirements.txt

5. run pip install dotenv

6. run pip install flask_sqlalchemy

7. run python seed.py (if there is no seed data generated)

8. Create a .env file, name the variable for the open AI API key as: OPENAI_API_KEY and set it equal to your own OPENAI key. If yours doesn't work, I am happy to provide mine for temporary use. Put the .env file in the helix_app folder

9. run python run.py


(Note: Have your own API key for OPENAI_API_KEY, if for some reason you cannot get one, please do let me know)


This will only run the backend server, you must run the frontend repo with this repo for the application to work. Do not click on the link in backend terminal
