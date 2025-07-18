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
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

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

 # NOVO (TESTE)
class UsuarioResponse(BaseModel):
    ID: int
    Email: str
    class Config:
        from_attributes = True

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

class AgendaBase(BaseModel):
    medico_id: int  # FK para Medico.UsuarioID
    paciente_id: int  # FK para Paciente.UsuarioID
    data_inicio: datetime
    data_fim: datetime
    status: str = "Agendada"

class AgendaCreate(AgendaBase):
    pass

class AgendaResponse(AgendaBase):
    id: int  # PK da tabela
    class Config:
        from_attributes = True

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
#def criar_paciente(paciente: Paciente):
#    conn = None
#    cursor = None
#    try:
#        conn = get_connection()
#        cursor = conn.cursor()
#        cursor.execute(
#            "INSERT INTO Paciente (UsuarioID, Nome, DataNascimento, CPF) VALUES (?, ?, ?, ?)", 
#            (paciente.usuario_id, paciente.nome, paciente.data_nascimento, paciente.cpf)
#        )
#        conn.commit()
#        return {"msg": "Paciente criado"}
#    except pyodbc.IntegrityError as e:
#        raise HTTPException(status_code=400, detail="CPF já cadastrado ou usuário inválido")
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=str(e))
#    finally:
#        if cursor:
#            cursor.close()
#        if conn:
#            conn.close()
def criar_paciente(paciente: Paciente):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO Paciente (
                UsuarioID, Nome, DataNascimento, CPF
            ) 
            OUTPUT INSERTED.UsuarioID
            VALUES (?, ?, ?, ?)""", 
            (
                paciente.usuario_id, paciente.nome, 
                paciente.data_nascimento, paciente.cpf
            )
        )
        paciente_id = cursor.fetchone()[0]  # Retorna o UsuarioID inserido
        conn.commit()
        return {"id": paciente_id, "msg": "Paciente criado"}
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
#def listar_pacientes():
#    conn = None
#    cursor = None
#    try:
#        conn = get_connection()
#        cursor = conn.cursor()
#        cursor.execute("SELECT ID, UsuarioID, Nome, CPF, DataNascimento FROM Paciente")
#        columns = [column[0] for column in cursor.description]
#        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
#        return data
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=str(e))
#    finally:
#        if cursor:
#            cursor.close()
#        if conn:
#            conn.close()
def listar_pacientes(usuario_id: Optional[int] = None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if usuario_id:
            cursor.execute("""
                SELECT 
                    UsuarioID as id,
                    Nome as nome,
                    DataNascimento as data_nascimento,
                    CPF as cpf
                FROM Paciente 
                WHERE UsuarioID = ?
            """, (usuario_id,))
        else:
            cursor.execute("""
                SELECT 
                    UsuarioID as id,
                    Nome as nome,
                    DataNascimento as data_nascimento,
                    CPF as cpf
                FROM Paciente
            """)
            
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        if usuario_id and not data:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
            
        return data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/medicos/{usuario_id}")
def obter_medico(usuario_id: int):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                UsuarioID as id,
                Nome as nome,
                Especialidade as especialidade,
                CRM as crm,
                Logradouro as logradouro,
                Cidade as cidade,
                CEP as cep
            FROM Medico 
            WHERE UsuarioID = ?
        """, (usuario_id,))
        
        medico = cursor.fetchone()
        if not medico:
            raise HTTPException(status_code=404, detail="Médico não encontrado")
            
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, medico))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/pacientes/{usuario_id}")
def obter_paciente(usuario_id: int):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                UsuarioID as id,
                Nome as nome,
                DataNascimento as data_nascimento,
                CPF as cpf
            FROM Paciente 
            WHERE UsuarioID = ?
        """, (usuario_id,))
        
        paciente = cursor.fetchone()
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
            
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, paciente))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==== MEDICO ====
@app.post("/medicos")
#def criar_medico(medico: Medico):
#    conn = None
#    cursor = None
#    try:
#        conn = get_connection()
#        cursor = conn.cursor()
#        cursor.execute(
#            "INSERT INTO Medico (UsuarioID, Nome, Especialidade, CRM, Logradouro, Cidade, CEP) VALUES (?, ?, ?, ?, ?, ?, ?)", 
#            (medico.usuario_id, medico.nome, medico.especialidade, medico.crm, medico.logradouro, medico.cidade, medico.cep)
#        )
#        conn.commit()
#        return {"msg": "Médico criado"}
#    except pyodbc.IntegrityError as e:
#        raise HTTPException(status_code=400, detail="CRM já cadastrado ou usuário inválido")
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=str(e))
#    finally:
#        if cursor:
#            cursor.close()
#        if conn:
#            conn.close()
def criar_medico(medico: Medico):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO Medico (
                UsuarioID, Nome, Especialidade, CRM, 
                Logradouro, Cidade, CEP
            ) 
            OUTPUT INSERTED.UsuarioID
            VALUES (?, ?, ?, ?, ?, ?, ?)""", 
            (
                medico.usuario_id, medico.nome, medico.especialidade, 
                medico.crm, medico.logradouro, medico.cidade, medico.cep
            )
        )
        medico_id = cursor.fetchone()[0]
        conn.commit()
        return {"id": medico_id, "msg": "Médico criado"}
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
#def listar_medicos():
#    conn = None
#    cursor = None
#    try:
#        conn = get_connection()
#        cursor = conn.cursor()
#        cursor.execute("SELECT ID, UsuarioID, Nome, Especialidade, CRM, Logradouro, Cidade, CEP FROM Medico")
#        columns = [column[0] for column in cursor.description]
#        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
#        return data
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=str(e))
#    finally:
#        if cursor:
#            cursor.close()
#        if conn:
#            conn.close()
# Adicione este novo endpoint na seção de médicos
#@app.get("/medicos/")
def listar_medicos(usuario_id: Optional[int] = None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if usuario_id:
            cursor.execute("""
                SELECT 
                    UsuarioID as id,
                    Nome as nome,
                    Especialidade as especialidade,
                    CRM as crm,
                    Logradouro as logradouro,
                    Cidade as cidade,
                    CEP as cep
                FROM Medico 
                WHERE UsuarioID = ?
            """, (usuario_id,))
        else:
            cursor.execute("""
                SELECT 
                    UsuarioID as id,
                    Nome as nome,
                    Especialidade as especialidade,
                    CRM as crm,
                    Logradouro as logradouro,
                    Cidade as cidade,
                    CEP as cep
                FROM Medico
            """)
            
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        if usuario_id and not data:
            raise HTTPException(status_code=404, detail="Médico não encontrado")
            
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

@app.post("/agendas/", response_model=AgendaResponse, tags=["Agendamentos"])
def criar_agendamento(agenda: AgendaCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Debug: Log dos dados recebidos
        print(f"Dados recebidos para agendamento: {agenda.dict()}")
    try:
        # Verifica se médico existe
        cursor.execute("SELECT 1 FROM Medico WHERE UsuarioID = ?", (agenda.medico_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Médico não encontrado")
        
        # Verifica se paciente existe
        cursor.execute("SELECT 1 FROM Paciente WHERE UsuarioID = ?", (agenda.paciente_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Paciente não encontrado")
        
        # Insere e retorna o ID gerado
        cursor.execute(
            """INSERT INTO Agenda (
                MedicoID, 
                PacienteID, 
                DataInicio, 
                DataFim, 
                Status
            ) 
            OUTPUT INSERTED.ID, INSERTED.MedicoID, INSERTED.PacienteID, 
                   INSERTED.DataInicio, INSERTED.DataFim, INSERTED.Status
            VALUES (?, ?, ?, ?, ?)""",
            (
                agenda.medico_id,
                agenda.paciente_id,
                agenda.data_inicio,
                agenda.data_fim,
                agenda.status
            )
        )
        
        # Obtém todos os dados inseridos
        inserted_data = cursor.fetchone()
        conn.commit()
        
        # Mapeia para o modelo de resposta
        return {
            "id_agenda": inserted_data[0],
            "medico_id": inserted_data[1],
            "paciente_id": inserted_data[2],
            "data_inicio": inserted_data[3],
            "data_fim": inserted_data[4],
            "status": inserted_data[5]
        }
        
    except pyodbc.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Erro de integridade: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/agendas/{agenda_id}", response_model=AgendaResponse, tags=["Agendamentos"])
def obter_agendamento(agenda_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT 
                ID,
                MedicoID,
                PacienteID,
                DataInicio,
                DataFim,
                Status
            FROM Agenda
            WHERE ID = ?""",
            (agenda_id,)
        )
        
        agenda = cursor.fetchone()
        if not agenda:
            raise HTTPException(status_code=404, detail="Agendamento não encontrado")
        
        return {
            "id_agenda": agenda[0],
            "medico_id": agenda[1],
            "paciente_id": agenda[2],
            "data_inicio": agenda[3],
            "data_fim": agenda[4],
            "status": agenda[5]
        }
    finally:
        cursor.close()
        conn.close()


@app.get("/agendas/", response_model=list[AgendaResponse], tags=["Agendamentos"])
def listar_agendamentos():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT 
                ID,
                MedicoID,
                PacienteID,
                DataInicio,
                DataFim,
                Status
            FROM Agenda"""
        )
        
        return [
            {
                "id_agenda": row[0],
                "medico_id": row[1],
                "paciente_id": row[2],
                "data_inicio": row[3],
                "data_fim": row[4],
                "status": row[5]
            }
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()
        conn.close()

def salvar_mensagem_no_banco(conversa_id: int, remetente_id: int, texto: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO Mensagem (ConversaID, RemetenteUsuarioID, Texto, DataEnvio, Lido) 
            VALUES (?, ?, ?, GETDATE(), 0)""",
            (conversa_id, remetente_id, texto)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

@app.post("/conversas/", tags=["Chat"])
async def criar_conversa(conversa_data: ConversaCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verifica quem é médico e quem é paciente
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN m.UsuarioID IS NOT NULL THEN 1 ELSE 0 END) as medicos,
                SUM(CASE WHEN p.UsuarioID IS NOT NULL THEN 1 ELSE 0 END) as pacientes
            FROM (VALUES (?), (?)) AS users(id)
            LEFT JOIN Medico m ON users.id = m.UsuarioID
            LEFT JOIN Paciente p ON users.id = p.UsuarioID
        """, (conversa_data.id_usuario1, conversa_data.id_usuario2))
        
        counts = cursor.fetchone()
        if counts[0] != 1 or counts[1] != 1:
            raise HTTPException(status_code=400, detail="Deve haver exatamente 1 médico e 1 paciente")
        
        # Identifica quem é médico e quem é paciente
        cursor.execute("SELECT UsuarioID FROM Medico WHERE UsuarioID IN (?, ?)", 
                      (conversa_data.id_usuario1, conversa_data.id_usuario2))
        medico_id = cursor.fetchone()[0]
        paciente_id = conversa_data.id_usuario2 if conversa_data.id_usuario1 == medico_id else conversa_data.id_usuario1
        
        # Verifica se conversa já existe
        cursor.execute(
            "SELECT ID FROM Conversa WHERE MedicoUsuarioID = ? AND PacienteUsuarioID = ?",
            (medico_id, paciente_id)
        )
        if existente := cursor.fetchone():
            return {"conversa_id": existente[0], "status": "existente"}
        
        # Cria nova conversa
        cursor.execute(
            "INSERT INTO Conversa (MedicoUsuarioID, PacienteUsuarioID) OUTPUT INSERTED.ID VALUES (?, ?)",
            (medico_id, paciente_id)
        )
        novo_id = cursor.fetchone()[0]
        conn.commit()
        return {"conversa_id": novo_id, "status": "criada"}
        
    except pyodbc.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.websocket("/ws/{conversa_id}/{usuario_id}")
async def websocket_endpoint(websocket: WebSocket, conversa_id: int, usuario_id: int):
    await manager.connect(websocket, usuario_id)
    try:
        while True:
            data = await websocket.receive_json()
            
            # Verifica se o usuário tem permissão nesta conversa
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM Conversa WHERE ID = ? AND (MedicoUsuarioID = ? OR PacienteUsuarioID = ?)",
                (conversa_id, usuario_id, usuario_id)
            )
            if not cursor.fetchone():
                await websocket.send_json({"error": "Acesso não autorizado"})
                continue
                
            # Salva mensagem e envia
            salvar_mensagem_no_banco(conversa_id, usuario_id, data['texto'])
            
            # Identifica o destinatário
            cursor.execute(
                "SELECT MedicoUsuarioID, PacienteUsuarioID FROM Conversa WHERE ID = ?",
                (conversa_id,)
            )
            medico_id, paciente_id = cursor.fetchone()
            destinatario_id = paciente_id if usuario_id == medico_id else medico_id
            
            mensagem = {
                "conversa_id": conversa_id,
                "remetente_id": usuario_id,
                "texto": data['texto'],
                "data_envio": datetime.now().isoformat()
            }
            
            await manager.send_personal_message(json.dumps(mensagem), destinatario_id)
            
    except WebSocketDisconnect:
        manager.disconnect(usuario_id)
    except Exception as e:
        print(f"Erro no WebSocket: {e}")
    finally:
        manager.disconnect(usuario_id)

@app.get("/historico/{conversa_id}", tags=["Chat"])
async def get_historico(conversa_id: int):
    """
    Busca no banco de dados todas as mensagens de uma conversa específica,
    ordenadas da mais antiga para a mais nova.
    """
    # 1. Pede uma conexão com o banco de dados
    conn = get_connection() # ou get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Serviço indisponível.")
    
    cursor = conn.cursor()
    
    # 2. Prepara a consulta SQL
    # Seleciona todas as colunas (*) da tabela 'Mensagem'
    # Filtra para pegar apenas as mensagens onde o 'ConversaID' corresponde ao ID recebido
    # Ordena os resultados pela 'DataEnvio' para que o chat apareça na ordem correta
    sql = "SELECT * FROM Mensagem WHERE ConversaID = ? ORDER BY DataEnvio ASC"
    
    # 3. Executa a consulta de forma segura
    cursor.execute(sql, conversa_id)
    
    # 4. Formata os resultados para o formato JSON
    # Pega o nome das colunas (ID, Texto, etc.)
    columns = [column[0] for column in cursor.description]
    # Cria uma lista de dicionários, onde cada dicionário representa uma mensagem
    historico = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # 5. Fecha a conexão com o banco
    conn.close()
    
    # 6. Retorna a lista de mensagens (o histórico)
    return historico

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
