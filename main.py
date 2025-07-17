from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from database import get_connection
from fastapi.middleware.cors import CORSMiddleware 
import requests
import uuid
import json
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pyodbc

app = FastAPI()

@app.get("/testar-email")
async def teste_email():
    print("\n=== INICIANDO TESTE DE EMAIL ===")  # Debug 0
    resultado = enviar_email_boas_vindas("f3rrazin@gmail.com", "Teste Azure")
    print(f"=== RESULTADO: {resultado} ===")  # Debug 11
    return {"status": "sucesso" if resultado else "falha"}

@app.get("/verificar-variaveis")
async def verificar_variaveis():
    return {
        "SMTP_USER": os.environ.get("SMTP_USER"),
        "SMTP_SERVER": os.environ.get("SMTP_SERVER"),
        "SMTP_PORT": os.environ.get("SMTP_PORT")
    }

@app.get("/testar-conexao")
def testar_conexao():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        conn.close()
        return {"status": "Conexão bem-sucedida", "resultado": result[0]}
    except Exception as e:
        return {"status": "Erro na conexão", "detalhes": str(e)}

# Configuração do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==== MODELS ====
class Usuario(BaseModel):
    email: str
    senha: str

class Paciente(BaseModel):
    usuario_id: int
    nome: str
    data_nascimento: str
    cpf: str

class Medico(BaseModel):
    usuario_id: int
    nome: str
    especialidade: str
    crm: str
    logradouro: str
    cidade: str
    cep: str

class Agenda(BaseModel):
    medico_id: int
    paciente_id: int
    data_inicio: str
    data_fim: str
    status: str = "Agendada"

class Conversa(BaseModel):
    medico_usuario_id: int
    paciente_usuario_id: int

class Mensagem(BaseModel):
    conversa_id: int
    remetente_usuario_id: int
    texto: str
    
class PacienteComUsuario(BaseModel):
    email: str
    senha: str
    nome: str
    cpf: str
    data_nascimento: str

# ==== USUARIO ====
@app.post("/pacientes-com-usuario")
def cadastrar_paciente_com_usuario(dados: PacienteComUsuario):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Inserir usuário e obter ID (SQL Server usa OUTPUT INSERTED)
        cursor.execute(
            "INSERT INTO Usuario (Email, Senha) OUTPUT INSERTED.ID VALUES (?, ?)", 
            (dados.email, dados.senha)
        )
        usuario_id = cursor.fetchone()[0]
        
        # Inserir paciente
        cursor.execute(
            "INSERT INTO Paciente (UsuarioID, Nome, CPF, DataNascimento) VALUES (?, ?, ?, ?)", 
            (usuario_id, dados.nome, dados.cpf, dados.data_nascimento)
        )
        
        conn.commit()
        enviar_email_boas_vindas(dados.email, dados.nome)
        return {"mensagem": "Paciente cadastrado com sucesso!", "usuario_id": usuario_id}

    except pyodbc.IntegrityError as e:
        raise HTTPException(status_code=400, detail="Email ou CPF já cadastrado")
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.post("/usuarios")
def criar_usuario(usuario: Usuario):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Usuario (Email, Senha) OUTPUT INSERTED.ID VALUES (?, ?)", 
            (usuario.email, usuario.senha)
        )
        usuario_id = cursor.fetchone()[0]
        conn.commit()
        return {"usuario_id": usuario_id}
    except pyodbc.IntegrityError as e:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/usuarios")
def listar_usuarios():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ID, Email FROM Usuario")
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.delete("/usuarios/{usuario_id}")
def deletar_usuario(usuario_id: int):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Usuario WHERE ID = ?", (usuario_id,))
        conn.commit()
        return {"msg": "Usuário deletado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==== PACIENTE ====
@app.post("/pacientes")
def criar_paciente(paciente: Paciente):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Paciente (UsuarioID, Nome, DataNascimento, CPF) VALUES (?, ?, ?, ?)", 
            (paciente.usuario_id, paciente.nome, paciente.data_nascimento, paciente.cpf)
        )
        conn.commit()
        return {"msg": "Paciente criado"}
    except pyodbc.IntegrityError as e:
        raise HTTPException(status_code=400, detail="CPF já cadastrado ou usuário inválido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/pacientes")
def listar_pacientes():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ID, UsuarioID, Nome, CPF, DataNascimento FROM Paciente")
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==== MEDICO ====
@app.post("/medicos")
def criar_medico(medico: Medico):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Medico (UsuarioID, Nome, Especialidade, CRM, Logradouro, Cidade, CEP) VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (medico.usuario_id, medico.nome, medico.especialidade, medico.crm, medico.logradouro, medico.cidade, medico.cep)
        )
        conn.commit()
        return {"msg": "Médico criado"}
    except pyodbc.IntegrityError as e:
        raise HTTPException(status_code=400, detail="CRM já cadastrado ou usuário inválido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/medicos")
def listar_medicos():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ID, UsuarioID, Nome, Especialidade, CRM, Logradouro, Cidade, CEP FROM Medico")
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.post("/login")
async def login(request: Request):
    dados = await request.json()
    email = dados.get("email")
    senha = dados.get("senha")
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT ID FROM Usuario WHERE Email = ? AND Senha = ?", (email, senha))
        user = cursor.fetchone()

        if not user:
            return {"success": False, "message": "Credenciais inválidas"}

        user_id = user[0]

        cursor.execute("SELECT 1 FROM Paciente WHERE UsuarioID = ?", (user_id,))
        is_patient = cursor.fetchone()

        return {
            "success": True,
            "tipo": "paciente" if is_patient else "medico"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==== AGENDA ====
@app.post("/agendas")
def criar_agendamento(agenda: Agenda):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Agenda (MedicoID, PacienteID, DataInicio, DataFim, Status) VALUES (?, ?, ?, ?, ?)", 
            (agenda.medico_id, agenda.paciente_id, agenda.data_inicio, agenda.data_fim, agenda.status)
        )
        conn.commit()
        return {"msg": "Agendamento criado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/agendas")
def listar_agendamentos():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ID, MedicoID, PacienteID, DataInicio, DataFim, Status FROM Agenda")
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==== CONVERSA ====
@app.post("/conversas")
def criar_conversa(conversa: Conversa):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Conversa (MedicoUsuarioID, PacienteUsuarioID) VALUES (?, ?)", 
            (conversa.medico_usuario_id, conversa.paciente_usuario_id)
        )
        conn.commit()
        return {"msg": "Conversa criada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/conversas")
def listar_conversas():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ID, MedicoUsuarioID, PacienteUsuarioID FROM Conversa")
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==== MENSAGEM ====
@app.post("/mensagens")
def enviar_mensagem(msg: Mensagem):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Mensagem (ConversaID, RemetenteUsuarioID, Texto) VALUES (?, ?, ?)", 
            (msg.conversa_id, msg.remetente_usuario_id, msg.texto)
        )
        conn.commit()
        return {"msg": "Mensagem enviada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/mensagens")
def listar_mensagens():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ID, ConversaID, RemetenteUsuarioID, Texto, DataEnvio FROM Mensagem")
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def enviar_email_boas_vindas(destinatario, nome):
    try:
        # Obter configurações do ambiente
        remetente = os.environ.get("SMTP_USER")
        senha = os.environ.get("SMTP_PASSWORD")
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", 587))
        
        print(f"Tentando enviar email para {destinatario} via {smtp_server}:{smtp_port}")

        if not remetente or not senha:
            print("Erro: SMTP_USER ou SMTP_PASSWORD não configurados")
            return False

        # Criar mensagem
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Bem-vindo ao MedFinder!"
        msg["From"] = remetente
        msg["To"] = destinatario

        html = f"""
        <html>
          <body>
            <p>Olá, {nome}!<br>
               Seja bem-vindo ao MedFinder. Sua conta foi criada com sucesso!
            </p>
          </body>
        </html>
        """

        msg.attach(MIMEText(html, "html"))

        # Enviar email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(remetente, senha)
            server.sendmail(remetente, destinatario, msg.as_string())
        
        print("Email enviado com sucesso!")
        return True
        
    except smtplib.SMTPException as e:
        print(f"Erro SMTP: {str(e)}")
    except Exception as e:
        print(f"Erro inesperado: {str(e)}")
    
    return False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
