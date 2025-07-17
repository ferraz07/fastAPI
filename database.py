import pyodbc

# Substitua pelos seus dados reais
server = 'medserverufsj.database.windows.net'
database = 'medfinderBD'
username = 'admin_medfinder'
password = 'SuaSenhaMuitoForte123!'
driver = '{ODBC Driver 17 for SQL Server}'

connection_string = f"""
    DRIVER={driver};
    SERVER={server};
    DATABASE={database};
    UID={username};
    PWD={password};
    Encrypt=yes;
    TrustServerCertificate=no;
    Connection Timeout=30;
"""

def get_connection():
    return pyodbc.connect(connection_string)
