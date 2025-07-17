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

@app.get("/health")
async def health_check():
    return {"status": "OK", "message": "App is running"}

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

class AgendaCreate(BaseModel):
    medico_id: int
    paciente_id: int
    data_inicio: str
    data_fim: str
    status: str = "Agendada"

class ConversaCreate(BaseModel):
    id_usuario1: int
    id_usuario2: int

class MensagemCreate(BaseModel):
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

@app.post("/agendas/", tags=["Agendamentos"])
def criar_agendamento(agenda: AgendaCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verifica se médico existe
        cursor.execute("SELECT 1 FROM Medico WHERE UsuarioID = ?", (agenda.medico_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Médico não encontrado")
        
        # Verifica se paciente existe
        cursor.execute("SELECT 1 FROM Paciente WHERE UsuarioID = ?", (agenda.paciente_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        cursor.execute(
            """INSERT INTO Agenda (MedicoID, PacienteID, DataInicio, DataFim, Status) 
            OUTPUT INSERTED.ID 
            VALUES (?, ?, ?, ?, ?)""",
            (agenda.medico_id, agenda.paciente_id, agenda.data_inicio, agenda.data_fim, agenda.status)
        )
        novo_id = cursor.fetchone()[0]
        conn.commit()
        return {"id": novo_id, **agenda.model_dump()}
        
    except pyodbc.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Erro de integridade: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/agendas/", tags=["Agendamentos"])
def listar_agendamentos():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                a.ID,
                a.MedicoID,
                m.Nome AS MedicoNome,
                a.PacienteID,
                p.Nome AS PacienteNome,
                a.DataInicio,
                a.DataFim,
                a.Status
            FROM Agenda a
            JOIN Medico m ON a.MedicoID = m.UsuarioID
            JOIN Paciente p ON a.PacienteID = p.UsuarioID
        """)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()
    
# --- CHAT (Lógica do WebSocket e API de Suporte) ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"Usuário {user_id} online.")

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"Usuário {user_id} offline.")

    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

manager = ConnectionManager()

@app.post("/conversas/", tags=["Chat"], summary="Cria uma nova conversa")
async def criar_conversa(conversa_data: ConversaCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    id1, id2 = conversa_data.id_usuario1, conversa_data.id_usuario2
    
    cursor.execute("SELECT UsuarioID FROM Medico WHERE UsuarioID IN (?, ?)", (id1, id2))
    medico_check = cursor.fetchall()
    cursor.execute("SELECT UsuarioID FROM Paciente WHERE UsuarioID IN (?, ?)", (id1, id2))
    paciente_check = cursor.fetchall()

    if len(medico_check) != 1 or len(paciente_check) != 1:
        conn.close()
        raise HTTPException(status_code=404, detail="É necessário um ID de médico válido e um ID de paciente válido.")

    medico_id, paciente_id = medico_check[0][0], paciente_check[0][0]
    
    cursor.execute("SELECT ID FROM Conversa WHERE MedicoUsuarioID = ? AND PacienteUsuarioID = ?", medico_id, paciente_id)
    if existente := cursor.fetchone():
        conn.close()
        return {"conversa_id": existente[0], "status": "existente"}
    
    cursor.execute("INSERT INTO Conversa (MedicoUsuarioID, PacienteUsuarioID) OUTPUT INSERTED.ID VALUES (?, ?)", medico_id, paciente_id)
    novo_id = cursor.fetchone()[0]
    conn.close()
    return {"conversa_id": novo_id, "status": "criada"}

@app.get("/usuarios/{usuario_id}/conversas", tags=["Chat"], summary="Lista as conversas de um usuário")
async def get_conversas_por_usuario(usuario_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = """
        SELECT C.ID AS ConversaID, C.MedicoUsuarioID, M.Nome AS MedicoNome, C.PacienteUsuarioID, P.Nome AS PacienteNome
        FROM Conversa AS C
        JOIN Medico AS M ON C.MedicoUsuarioID = M.UsuarioID
        JOIN Paciente AS P ON C.PacienteUsuarioID = P.UsuarioID
        WHERE C.MedicoUsuarioID = ? OR C.PacienteUsuarioID = ?
    """
    cursor.execute(sql, usuario_id, usuario_id)
    conversas = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    conn.close()
    return conversas

@app.get("/historico/{conversa_id}", tags=["Chat"], summary="Busca o histórico de uma conversa")
async def get_historico_conversa(conversa_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Mensagem WHERE ConversaID = ? ORDER BY DataEnvio ASC", conversa_id)
    historico = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    conn.close()
    return historico

@app.websocket("/ws/{conversa_id}/{usuario_id}")
async def websocket_endpoint(websocket: WebSocket, conversa_id: int, usuario_id: int):
    await manager.connect(websocket, usuario_id)
    try:
        while True:
            data = await websocket.receive_json()
            salvar_mensagem_no_banco(conversa_id, usuario_id, data['texto'])
            mensagem_para_enviar = {"remetente_id": usuario_id, "texto": data['texto']}
            await manager.send_personal_message(json.dumps(mensagem_para_enviar), data['destinatario_id'])
    except WebSocketDisconnect:
        manager.disconnect(usuario_id)
    except Exception as e:
        print(f"Ocorreu um erro no WebSocket: {e}")
        manager.disconnect(usuario_id)

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
