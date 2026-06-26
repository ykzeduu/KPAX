import psycopg2
from psycopg2.extras import RealDictCursor
import urllib.parse
import uuid
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from http.cookies import SimpleCookie

# ==========================================
# ======= CONFIGURAÇÕES E BANCO ============
# ==========================================

DATABASE_URL = os.environ.get("DATABASE_URL")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

SESSIONS = {}

def init_db():
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    
    # Tabela de solicitações
    c.execute('''
        CREATE TABLE IF NOT EXISTS solicitacao (
            id SERIAL PRIMARY KEY,
            cod_cliente TEXT NOT NULL,
            cliente_razao TEXT NOT NULL,
            equipamentos TEXT NOT NULL,
            data TEXT NOT NULL,
            status TEXT DEFAULT 'Restabelecer',
            contato TEXT,
            solicitante TEXT,
            obs_improdutivo TEXT,
            resolvido_por TEXT
        )
    ''')
    
    # Tabela de Usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # Lista de usuários padrão definidos para o sistema
    usuarios_padrao = [
        ("admin", "123", "admin"),
        ("kauangsm", "!KauanMnhaw02062003@", "admin"),
        ("julianagsm", "Gsmcopytec@2026", "admin"),
        ("heloisa", "contratos@2026", "comum"),
        ("andressa", "contratos@2026", "comum"),
        ("pedro", "contratos@2026", "comum")
    ]
    
    for u, s, r in usuarios_padrao:
        c.execute("INSERT INTO usuarios (username, senha, role) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING", (u, s, r))
        
    conn.commit()
    conn.close()

# Executa a inicialização do banco seguro na nuvem
try:
    if DATABASE_URL:
        init_db()
except Exception as e:
    print(f"Aviso de banco inicial: {e}")

# ==========================================
# ============ TEMPLATES HTML ==============
# ==========================================

def render_base(title, content, session_data=None, message="", msg_type="info"):
    nav = ""
    auto_refresh_script = ""
    
    if session_data:
        admin_nav = ""
        if session_data['role'] == 'admin':
            admin_nav = f'<a href="/usuarios" class="btn btn-sm btn-info text-white shadow-sm fw-bold"><i class="bi bi-people-fill me-1"></i> Usuários</a>'

        nav = f"""
        <div class="top-bar">
            <h4>
                <img src="/logo.jpg" alt="KPAX Logo">
                Controle do KPAX
            </h4>
            <div class="d-flex align-items-center gap-3">
                <span id="refresh-indicator" class="badge bg-success shadow-sm" style="font-size: 0.7rem;" title="Atualização Automática Ativa"><i class="bi bi-arrow-repeat"></i> Auto-Refresh</span>
                <button id="btn-dark-mode" class="btn btn-sm theme-toggle-btn shadow-sm" onclick="toggleDarkMode()" title="Alternar Tema Escuro/Claro"></button>
                <span class="user-badge"><i class="bi bi-person-circle me-1"></i> {session_data['usuario'].lower()} ({session_data['role']})</span>
                <div class="d-flex gap-1">
                    <a href="/" class="btn btn-sm btn-light fw-bold text-primary shadow-sm"><i class="bi bi-grid-fill me-1"></i> Painel</a>
                    <a href="/resolvidos" class="btn btn-sm btn-success shadow-sm fw-bold"><i class="bi bi-check-all me-1"></i> Resolvidos</a>
                    {admin_nav}
                    <a href="/alterar_senha" class="btn btn-sm btn-warning shadow-sm text-dark fw-bold"><i class="bi bi-key-fill me-1"></i> Senha</a>
                    <a href="/logout" class="btn btn-sm btn-danger shadow-sm fw-bold"><i class="bi bi-box-arrow-right me-1"></i> Sair</a>
                </div>
            </div>
        </div>
        """
        
        if title not in ["Alterar Senha", "Controle de Usuários"]:
            auto_refresh_script = """
            <script>
                window.isInteracting = false;
                const refreshIndicator = document.getElementById('refresh-indicator');
                
                setInterval(() => {
                    if (!window.isInteracting) {
                        window.location.reload();
                    }
                }, 30000);

                document.addEventListener('focusin', (e) => {
                    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) {
                        window.isInteracting = true;
                        if(refreshIndicator) {
                            refreshIndicator.classList.replace('bg-success', 'bg-warning');
                            refreshIndicator.classList.replace('text-white', 'text-dark');
                            refreshIndicator.innerHTML = '<i class="bi bi-pause-circle"></i> Pausado';
                        }
                    }
                });

                document.addEventListener('focusout', (e) => {
                    setTimeout(() => {
                        if (!['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
                            window.isInteracting = false;
                            if(refreshIndicator) {
                                refreshIndicator.classList.replace('bg-warning', 'bg-success');
                                refreshIndicator.classList.replace('text-dark', 'text-white');
                                refreshIndicator.innerHTML = '<i class="bi bi-arrow-repeat"></i> Auto-Refresh';
                            }
                        }
                    }, 500);
                });
            </script>
            """
        else:
            auto_refresh_script = """
            <script>
                const refreshIndicator = document.getElementById('refresh-indicator');
                if(refreshIndicator) refreshIndicator.style.display = 'none';
            </script>
            """
        
    msg_html = f'<div class="alert alert-{msg_type} shadow-sm mx-3 mt-3 border-0" style="border-radius: 10px;"><i class="bi bi-info-circle-fill me-2"></i>{message}</div>' if message else ""

    return f"""
    <!DOCTYPE html>
    <html lang="pt-br" id="html-root">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} | KPAX</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
        <script>
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-bs-theme', savedTheme);
        </script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            body {{ background-color: #f0f4f8; font-family: 'Inter', sans-serif; font-size: 0.9rem; padding-top: 85px; color: #2c3e50; transition: background-color 0.3s, color 0.3s; }}
            .top-bar {{ background: linear-gradient(135deg, #102a43 0%, #243b55 100%); position: fixed; top: 0; left: 0; width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 12px 30px; z-index: 1050; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            .top-bar h4 {{ color: white; margin: 0; font-size: 1.3rem; font-weight: 700; display: flex; align-items: center; letter-spacing: 0.5px; }}
            .top-bar h4 img {{ height: 35px; margin-right: 15px; border-radius: 4px; background: white; padding: 2px; }}
            .user-badge {{ background: rgba(255,255,255,0.1); padding: 5px 12px; border-radius: 20px; color: #e2e8f0; font-weight: 500; }}
            .card {{ border: none; border-radius: 16px; box-shadow: 0 6px 20px rgba(0,0,0,0.04); overflow: hidden; margin-bottom: 25px; transition: background-color 0.3s; }}
            .card-header {{ font-weight: 600; letter-spacing: 0.3px; border-bottom: none; padding: 15px 20px; }}
            .bg-kpax-primary {{ background: linear-gradient(135deg, #102a43 0%, #1a365d 100%); color: white; }}
            .btn {{ border-radius: 8px; font-weight: 500; transition: all 0.2s; }}
            .btn:hover {{ transform: translateY(-1px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
            .form-control, .form-select {{ border-radius: 8px; border: 1px solid #cbd5e1; padding: 0.5rem 0.75rem; }}
            .form-control:focus, .form-select:focus {{ border-color: #3b82f6; box-shadow: 0 0 0 0.25rem rgba(59, 130, 246, 0.25); }}
            .kpi-card {{ border-radius: 16px; color: white; text-align: center; padding: 1.5rem 1rem; box-shadow: 0 8px 15px rgba(0,0,0,0.1); transition: transform 0.3s; border: none; }}
            .kpi-card:hover {{ transform: translateY(-5px); }}
            .kpi-card h2 {{ font-size: 2.5rem; font-weight: 700; margin-top: 10px; margin-bottom: 0; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }}
            .kpi-card span {{ font-size: 1rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; opacity: 0.9; }}
            .kpi-restabelecer {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }}
            .kpi-improdutivo {{ background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%); }}
            .kpi-execucao {{ background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); }}
            .kpi-resolvido {{ background: linear-gradient(135deg, #10b981 0%, #047857 100%); }}
            .table {{ margin-bottom: 0; }}
            .table thead th {{ background-color: #f8fafc; color: #475569; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.5px; border-bottom: 2px solid #e2e8f0; padding: 12px 15px; }}
            .table tbody td {{ padding: 15px; vertical-align: middle; border-bottom: 1px solid #f1f5f9; color: #334155; }}
            .table tbody tr:hover {{ background-color: #f8fafc; }}
            .badge-status {{ padding: 6px 12px; border-radius: 20px; font-weight: 600; font-size: 0.75rem; letter-spacing: 0.5px; }}
            .status-restabelecer {{ background-color: #fef3c7; color: #d97706; }}
            .status-improdutivo {{ background-color: #fee2e2; color: #b91c1c; }}
            .status-execucao {{ background-color: #dbeafe; color: #1d4ed8; }}
            .status-resolvido {{ background-color: #d1fae5; color: #047857; }}
            .theme-toggle-btn {{ color: #475569; border: 1px solid #cbd5e1; background-color: #ffffff; }}
            .theme-toggle-btn:hover {{ background-color: #e2e8f0; color: #1e293b; }}
            .top-bar .theme-toggle-btn {{ color: #e2e8f0; border: 1px solid rgba(255,255,255,0.2); background-color: transparent; }}
            .top-bar .theme-toggle-btn:hover {{ background-color: rgba(255,255,255,0.1); color: #fff; }}
            .login-title {{ color: #102a43; }}
            [data-bs-theme="dark"] body {{ background-color: #121212; color: #e4e4e4; }}
            [data-bs-theme="dark"] .card {{ background-color: #1e1e1e; border: 1px solid #333; }}
            [data-bs-theme="dark"] .card-body.bg-white {{ background-color: #1e1e1e !important; }}
            [data-bs-theme="dark"] .card-header.bg-white {{ background-color: #1e1e1e !important; border-bottom: 1px solid #333 !important; }}
            [data-bs-theme="dark"] .text-dark {{ color: #e4e4e4 !important; }}
            [data-bs-theme="dark"] .login-title {{ color: #ffffff !important; }}
            [data-bs-theme="dark"] .table thead th {{ background-color: #2c2c2c; color: #e4e4e4; border-bottom: 2px solid #444; }}
            [data-bs-theme="dark"] .table tbody td {{ border-bottom: 1px solid #333; color: #ccc; }}
            [data-bs-theme="dark"] .table tbody tr:hover {{ background-color: #2a2a2a; }}
            [data-bs-theme="dark"] .form-control, [data-bs-theme="dark"] .form-select {{ background-color: #2c2c2c; color: #fff; border-color: #444; }}
            [data-bs-theme="dark"] .form-control::placeholder {{ color: #888; }}
            [data-bs-theme="dark"] .input-group-text {{ background-color: #333 !important; border-color: #444 !important; color: #ccc !important; }}
            [data-bs-theme="dark"] .theme-toggle-btn {{ color: #f59e0b; border-color: #f59e0b; background-color: transparent; }}
            [data-bs-theme="dark"] .theme-toggle-btn:hover {{ background-color: rgba(245, 158, 11, 0.1); color: #fbbf24; }}
        </style>
    </head>
    <body>
        {nav}
        <div class="container-fluid mt-2 px-4">
            {msg_html}
            {content}
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function applyTheme(theme) {{
                document.documentElement.setAttribute('data-bs-theme', theme);
                const btn = document.getElementById('btn-dark-mode');
                if(btn) {{
                    if(theme === 'dark') {{
                        btn.innerHTML = '<i class="bi bi-sun-fill"></i>';
                    }} else {{
                        btn.innerHTML = '<i class="bi bi-moon-stars"></i>';
                    }}
                }}
            }}
            
            function toggleDarkMode() {{
                const currentTheme = document.documentElement.getAttribute('data-bs-theme');
                const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                localStorage.setItem('theme', newTheme);
                applyTheme(newTheme);
            }}
            
            document.addEventListener('DOMContentLoaded', () => {{
                applyTheme(document.documentElement.getAttribute('data-bs-theme'));
            }});
        </script>
        {auto_refresh_script}
    </body>
    </html>
    """

def render_login(message="", msg_type="danger"):
    content = """
    <div class="row justify-content-center mt-5 pt-5">
        <div class="col-md-4">
            <div class="card shadow-lg border-0" style="border-radius: 20px; position: relative;">
                <div style="position: absolute; top: 20px; right: 20px; z-index: 10;">
                    <button id="btn-dark-mode" class="btn btn-sm theme-toggle-btn shadow-sm" onclick="toggleDarkMode()" title="Alternar Tema Escuro/Claro"></button>
                </div>
                <div class="card-body p-5 text-center">
                    <img src="/logo.jpg" alt="KPAX Logo" style="height: 80px; margin-bottom: 25px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                    <h4 class="mb-4 fw-bold login-title">Acesso ao Sistema</h4>
                    <form method="POST" action="/login" class="text-start">
                        <div class="mb-3">
                            <label class="form-label text-muted fw-semibold small">Usuário</label>
                            <div class="input-group">
                                <span class="input-group-text bg-light border-end-0"><i class="bi bi-person text-muted"></i></span>
                                <input type="text" name="usuario" class="form-control border-start-0 ps-0" placeholder="Digite seu usuário" required>
                            </div>
                        </div>
                        <div class="mb-4">
                            <label class="form-label text-muted fw-semibold small">Senha</label>
                            <div class="input-group">
                                <span class="input-group-text bg-light border-end-0"><i class="bi bi-lock text-muted"></i></span>
                                <input type="password" name="senha" class="form-control border-start-0 ps-0" placeholder="Digite sua senha" required>
                            </div>
                        </div>
                        <button type="submit" class="btn btn-primary w-100 py-2 fw-bold" style="background: linear-gradient(135deg, #102a43 0%, #3b82f6 100%); border: none; font-size: 1.1rem;">Entrar</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """
    return render_base("Login", content, message=message, msg_type=msg_type)

def render_alterar_senha(session_data, message="", msg_type="info"):
    content = """
    <div class="row justify-content-center mt-4">
        <div class="col-md-5">
            <div class="card shadow-sm">
                <div class="card-header bg-kpax-primary text-white">
                    <h5 class="mb-0 fw-bold"><i class="bi bi-key-fill me-2"></i> Alterar Minha Senha</h5>
                </div>
                <div class="card-body bg-white p-4">
                    <form method="POST" action="/alterar_senha">
                        <div class="mb-3">
                            <label class="form-label small text-muted fw-bold">Senha Atual</label>
                            <input type="password" name="senha_atual" class="form-control" placeholder="Sua senha atual de acesso" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label small text-muted fw-bold">Nova Senha</label>
                            <input type="password" name="nova_senha" class="form-control" placeholder="Escolha uma nova senha" required>
                        </div>
                        <div class="mb-4">
                            <label class="form-label small text-muted fw-bold">Confirmar Nova Senha</label>
                            <input type="password" name="confirmar_senha" class="form-control" placeholder="Repita a nova senha" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100 py-2 fw-bold" style="background: linear-gradient(135deg, #102a43 0%, #3b82f6 100%); border: none;">
                            <i class="bi bi-shield-check me-2"></i> ATUALIZAR MINHA SENHA
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """
    return render_base("Alterar Senha", content, session_data, message, msg_type)

def render_usuarios(session_data, usuarios_lista, message="", msg_type="info"):
    linhas = ""
    for uid, uname, pwd, role in usuarios_lista:
        btn_deletar = ""
        if uname != session_data['usuario']:
            btn_deletar = f"""
            <form action="/usuarios/deletar" method="POST" style="display:inline; margin:0;">
                <input type="hidden" name="id" value="{uid}">
                <button type="submit" class="btn btn-sm btn-light text-danger border" title="Excluir Conta" onclick="return confirm('Deseja mesmo remover permanentemente a conta de {uname}?')">
                    <i class="bi bi-trash3"></i>
                </button>
            </form>
            """
        
        badge_color = 'primary' if role == 'admin' else 'secondary'
        
        linhas += f"""
        <tr>
            <td><strong>{uid}</strong></td>
            <td><span class="user-badge bg-dark text-light" style="font-size:0.85rem;"><i class="bi bi-person me-1"></i>{uname}</span></td>
            <td>
                <div class="input-group input-group-sm" style="max-width: 250px;">
                    <input type="text" class="form-control bg-light text-dark fw-mono font-monospace" value="{pwd}" readonly>
                    <button class="btn btn-outline-secondary" type="button" onclick="navigator.clipboard.writeText('{pwd}'); alert('Senha copiada com sucesso!');" title="Copiar Senha">
                        <i class="bi bi-clipboard"></i>
                    </button>
                </div>
            </td>
            <td><span class="badge bg-{badge_color} px-2 py-2" style="font-size:0.75rem;">{role.upper()}</span></td>
            <td>
                <div class="btn-group shadow-sm">
                    <button class="btn btn-sm btn-light text-primary border" title="Editar Usuário" onclick="editarUsuario({uid}, '{uname}', '{pwd}', '{role}')"><i class="bi bi-pencil-square"></i></button>
                    {btn_deletar}
                </div>
            </td>
        </tr>
        """

    content = f"""
    <div class="row g-4">
        <div class="col-md-4">
            <div class="card shadow-sm">
                <div class="card-header bg-kpax-primary text-white d-flex justify-content-between align-items-center">
                    <span id="form-user-title" class="fw-bold"><i class="bi bi-person-plus-fill me-2"></i> Adicionar Conta</span>
                    <button type="button" class="btn btn-sm btn-light text-dark fw-bold" id="btn-cancelar-user" style="display:none;" onclick="cancelarEdicaoUsuario()">Cancelar</button>
                </div>
                <div class="card-body bg-white p-4">
                    <form method="POST" action="/usuarios/salvar" id="form-usuario">
                        <input type="hidden" name="id_usuario" id="id_usuario">
                        <div class="mb-3">
                            <label class="form-label small text-muted fw-bold">Nome de Usuário</label>
                            <input type="text" name="username" id="user_username" class="form-control" placeholder="Ex: marcos.silva" required autocomplete="off">
                        </div>
                        <div class="mb-3">
                            <label class="form-label small text-muted fw-bold">Senha de Acesso</label>
                            <input type="text" name="senha" id="user_senha" class="form-control" placeholder="Defina a senha" required autocomplete="off">
                        </div>
                        <div class="mb-4">
                            <label class="form-label small text-muted fw-bold">Nível de Permissão (Role)</label>
                            <select name="role" id="user_role" class="form-select" required>
                                <option value="comum">Comum (Apenas registro/leitura)</option>
                                <option value="admin">Admin (Controle total)</option>
                            </select>
                        </div>
                        <button type="submit" id="btn_submit_user" class="btn btn-primary w-100 py-2 fw-bold" style="background: linear-gradient(135deg, #102a43 0%, #3b82f6 100%); border: none;">
                            <i class="bi bi-save me-2"></i> SALVAR USUÁRIO
                        </button>
                    </form>
                </div>
            </div>
        </div>

        <div class="col-md-8">
            <div class="card shadow-sm">
                <div class="card-header bg-white border-bottom py-3">
                    <h5 class="mb-0 text-dark fw-bold"><i class="bi bi-people-fill text-primary me-2"></i> Visualização de Contas e Senhas Ativas</h5>
                </div>
                <div class="table-responsive">
                    <table class="table table-hover align-middle">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Usuário</th>
                                <th>Senha Atual</th>
                                <th>Perfil</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            {linhas}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
    function editarUsuario(id, username, senha, role) {{
        document.getElementById('id_usuario').value = id;
        document.getElementById('user_username').value = username;
        document.getElementById('user_senha').value = senha;
        document.getElementById('user_role').value = role;
        
        document.getElementById('form-user-title').innerHTML = "<i class='bi bi-pencil-square me-2'></i> Editando Conta: " + username;
        document.getElementById('btn-cancelar-user').style.display = 'block';
        
        const btn = document.getElementById('btn_submit_user');
        btn.innerHTML = "<i class='bi bi-check-circle me-2'></i> ATUALIZAR USUÁRIO";
        btn.style.background = "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)";
        
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}

    function cancelarEdicaoUsuario() {{
        location.reload();
    }}
    </script>
    """
    return render_base("Controle de Usuários", content, session_data, message, msg_type)

def render_index(session_data, kpis, solicitacoes, message=""):
    linhas_tabela = ""
    status_classes = {
        'Restabelecer': 'status-restabelecer',
        'Em Execução': 'status-execucao'
    }
    
    for req in solicitacoes:
        contato_val = req['contato'] if req['contato'] else "-"
        solicitante_val = req['solicitante'] if req['solicitante'] else "Não atribuído"
        status_atual = req['status']
        badge_class = status_classes.get(status_atual, 'bg-secondary text-white')
        
        admin_actions = ""
        if session_data['role'] == 'admin':
            sel_r = "selected" if status_atual == "Restabelecer" else ""
            sel_e = "selected" if status_atual == "Em Execução" else ""
            admin_actions = f"""
            <td>
                <form action="/atualizar_status" method="POST" class="d-flex flex-column gap-1" onsubmit="return validarStatus(this)">
                    <input type="hidden" name="id" value="{req['id']}">
                    <div class="d-flex gap-1"> 
                        <select name="status" class="form-select form-select-sm shadow-sm" style="width: 140px; border-radius: 6px;" onchange="toggleObsField(this, {req['id']})">
                            <option value="Restabelecer" {sel_r}>Restabelecer</option>
                            <option value="Em Execução" {sel_e}>Em Execução</option>
                            <option value="Improdutivo">Improdutivo</option>
                        </select>
                        <button type="submit" class="btn btn-sm btn-primary shadow-sm" title="Atualizar Status"><i class="bi bi-arrow-repeat"></i></button>
                        <button type="submit" name="btn_resolver" value="Resolvido" class="btn btn-sm btn-success shadow-sm" title="Marcar como Resolvido" onclick="this.form.bypassValidation = true;"><i class="bi bi-check-lg"></i></button>
                    </div>
                    <input type="text" name="obs_improdutivo" id="obs_{req['id']}" class="form-control form-control-sm mt-1" placeholder="Digite o motivo..." style="display: none; font-size:0.75rem;" autocomplete="off">
                </form>
            </td>
            """
            
        linhas_tabela += f"""
        <tr>
            <td><strong>{req['cod_cliente']}</strong></td>
            <td class="fw-medium">{req['cliente_razao']}</td>
            <td>{req['equipamentos']}</td>
            <td><i class="bi bi-telephone text-muted me-1"></i> {contato_val}</td>
            <td><i class="bi bi-person-badge text-primary me-1"></i> <strong>{solicitante_val}</strong></td>
            <td><i class="bi bi-calendar3 text-muted me-1"></i> {req['data']}</td>
            <td><span class="badge-status {badge_class}">{status_atual}</span></td>
            <td>
                <div class="btn-group shadow-sm">
                    <button class="btn btn-sm btn-light text-primary border" title="Editar" onclick="preencherEdicao({req['id']}, '{req['cod_cliente']}', '{req['cliente_razao']}', '{req['equipamentos']}', '{req['data']}', '{contato_val}')"><i class="bi bi-pencil-square"></i></button>
                    <form action="/deletar" method="POST" style="display:inline; margin:0;">
                        <input type="hidden" name="id" value="{req['id']}">
                        <button type="submit" class="btn btn-sm btn-light text-danger border" title="Excluir" onclick="return confirm('Tem certeza que deseja excluir esta solicitação?')"><i class="bi bi-trash3"></i></button>
                    </form>
                </div>
            </td>
            {admin_actions}
        </tr>
        """
        
    if not solicitacoes:
        col_span = "9" if session_data['role'] == 'admin' else "8"
        linhas_tabela = f"<tr><td colspan='{col_span}' class='text-center py-5 text-muted'><i class='bi bi-inbox fs-2 d-block mb-2'></i>Nenhuma solicitação ativa no momento.</td></tr>"
        
    admin_header = "<th>Gerenciar Status</th>" if session_data['role'] == 'admin' else ""
    
    content = f"""
    <div class="row g-4 mb-4">
        <div class="col-md-3">
            <div class="card kpi-card kpi-restabelecer">
                <span><i class="bi bi-arrow-clockwise me-2"></i> Restabelecer</span>
                <h2>{kpis.get('Restabelecer', 0)}</h2>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card kpi-card kpi-improdutivo">
                <span><i class="bi bi-exclamation-triangle-fill me-2"></i> Improdutivo</span>
                <h2>{kpis.get('Improdutivo', 0)}</h2>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card kpi-card kpi-execucao">
                <span><i class="bi bi-gear-fill me-2"></i> Em Execução</span>
                <h2>{kpis.get('Em Execução', 0)}</h2>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card kpi-card kpi-resolvido">
                <span><i class="bi bi-check-circle-fill me-2"></i> Concluídos</span>
                <h2>{kpis.get('Resolvido', 0)}</h2>
            </div>
        </div>
    </div>
    
    <div class="card shadow-sm">
        <div class="card-header bg-kpax-primary d-flex justify-content-between align-items-center">
            <span id="titulo-form" class="fs-5"><i class="bi bi-plus-circle me-2"></i> Nova Solicitação</span>
            <button type="button" class="btn btn-sm btn-light text-dark fw-bold" id="btn-cancelar" style="display:none;" onclick="cancelarEdicao()">Cancelar Edição</button>
        </div>
        <div class="card-body bg-white p-4">
            <form method="POST" action="/" id="form-ativo" class="row g-3">
                <input type="hidden" name="id_editar" id="id_editar">
                <div class="col-md-2">
                    <label class="form-label small text-muted fw-bold">Cód. Cliente</label>
                    <input type="text" name="cod_cliente" id="cod_cliente" class="form-control" placeholder="Ex: 12345" required>
                </div>
                <div class="col-md-3">
                    <label class="form-label small text-muted fw-bold">Razão Social</label>
                    <input type="text" name="cliente_razao" id="cliente_razao" class="form-control" placeholder="Razão social." required>
                </div>
                <div class="col-md-3">
                    <label class="form-label small text-muted fw-bold">Equipamentos</label>
                    <input type="text" name="equipamentos" id="equipamentos" class="form-control" placeholder="Série do equip." required>
                </div>
                <div class="col-md-2">
                    <label class="form-label small text-muted fw-bold">Contato</label>
                    <input type="text" name="contato" id="contato" class="form-control" placeholder="Tel/Nome (Opcional)">
                </div>
                <div class="col-md-2">
                    <label class="form-label small text-muted fw-bold">Data</label>
                    <input type="date" name="data" id="data" class="form-control" required>
                </div>
                <div class="col-12 mt-4">
                    <button type="submit" id="btn_submit_form" class="btn btn-primary w-100 py-2 fs-6 shadow-sm" style="background: linear-gradient(135deg, #102a43 0%, #3b82f6 100%); border: none;">
                        <i class="bi bi-save me-2"></i> REGISTRAR SOLICITAÇÃO
                    </button>
                </div>
            </form>
        </div>
    </div>
    
    <div class="card shadow-sm mt-4 mb-5">
        <div class="card-header bg-white border-bottom py-3">
            <h5 class="mb-0 text-dark fw-bold"><i class="bi bi-list-task text-primary me-2"></i> Solicitações em Andamento</h5>
        </div>
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Cód. Cliente</th>
                        <th>Razão Social</th>
                        <th>Equipamentos</th>
                        <th>Contato</th>
                        <th>Atendente</th>
                        <th>Data Registro</th>
                        <th>Status</th>
                        <th>Ações</th>
                        {admin_header}
                    </tr>
                </thead>
                <tbody>
                    {linhas_tabela}
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
    function preencherEdicao(id, cod, razao, equip, data, contato) {{
        document.getElementById('id_editar').value = id;
        document.getElementById('cod_cliente').value = cod;
        document.getElementById('cliente_razao').value = razao;
        document.getElementById('equipamentos').value = equip;
        document.getElementById('data').value = data;
        document.getElementById('contato').value = contato === '-' ? '' : contato;
        
        document.getElementById('titulo-form').innerHTML = "<i class='bi bi-pencil-square me-2'></i> Editando Registro";
        document.getElementById('btn-cancelar').style.display = 'block';
        
        const btn = document.getElementById('btn_submit_form');
        btn.innerHTML = "<i class='bi bi-check-circle me-2'></i> ATUALIZAR REGISTRO";
        btn.style.background = "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)";
        
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}
    function cancelarEdicao() {{
        location.reload();
    }}
    function toggleObsField(selectElement, id) {{
        const obsField = document.getElementById('obs_' + id);
        if(selectElement.value === 'Improdutivo') {{
            obsField.style.display = 'block';
            obsField.required = true;
        }} else {{
            obsField.style.display = 'none';
            obsField.required = false;
        }}
    }}
    function validarStatus(form) {{
        if(form.bypassValidation) return true;
        const select = form.querySelector('select[name="status"]');
        const obs = form.querySelector('input[name="obs_improdutivo"]');
        if(select.value === 'Improdutivo' && !obs.value.trim()) {{
            alert('Por favor, informe o motivo do status Improdutivo!');
            return false;
        }}
        return true;
    }}
    </script>
    """
    return render_base("Painel de Controle", content, session_data, message)

def render_resolvidos(session_data, solicitacoes, message=""):
    linhas_tabela = ""
    for req in solicitacoes:
        obs_val = f"<br><small class='text-danger fw-semibold'>Motivo: {req['obs_improdutivo']}</small>" if req['obs_improdutivo'] else ""
        atendente = req['resolvido_por'] if req['resolvido_por'] else "Sistema"
        
        badge_status = ""
        if req['status'] == 'Resolvido':
            badge_status = '<span class="badge-status status-resolvido">Resolvido</span>'
        else:
            badge_status = '<span class="badge-status status-improdutivo">Improdutivo</span>'

        btn_retroceder = ""
        if session_data['role'] == 'admin':
            btn_retroceder = f"""
            <form action="/retroceder" method="POST" style="display:inline; margin:0;">
                <input type="hidden" name="id" value="{req['id']}">
                <button type="submit" class="btn btn-sm btn-light text-warning border" title="Mover de volta para Andamento" onclick="return confirm('Deseja retornar esta solicitação ao painel ativo?')">
                    <i class="bi bi-arrow-left-right"></i> Reativar
                </button>
            </form>
            """

        linhas_tabela += f"""
        <tr>
            <td><strong>{req['cod_cliente']}</strong></td>
            <td class="fw-medium">{req['cliente_razao']}</td>
            <td>{req['equipamentos']}</td>
            <td><i class="bi bi-calendar3 text-muted me-1"></i> {req['data']}</td>
            <td>{badge_status}{obs_val}</td>
            <td><span class="user-badge bg-secondary text-light" style="font-size:0.8rem;"><i class="bi bi-person-check me-1"></i>{atendente.lower()}</span></td>
            <td>
                {btn_retroceder}
            </td>
        </tr>
        """

    if not solicitacoes:
        linhas_tabela = "<tr><td colspan='7' class='text-center py-5 text-muted'><i class='bi bi-folder-x fs-2 d-block mb-2'></i>Nenhum registro finalizado no histórico.</td></tr>"

    content = f"""
    <div class="card shadow-sm mt-2 mb-5">
        <div class="card-header bg-success text-white py-3">
            <h5 class="mb-0 fw-bold"><i class="bi bi-check-all me-2"></i> Histórico de Solicitações Finalizadas (Resolvidos / Improdutivos)</h5>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle">
                <thead>
                    <tr>
                        <th>Cód. Cliente</th>
                        <th>Razão Social</th>
                        <th>Equipamentos</th>
                        <th>Data Registro</th>
                        <th>Resultado</th>
                        <th>Finalizado Por</th>
                        <th>Ações</th>
                    </tr>
                </thead>
                <tbody>
                    {linhas_tabela}
                </tbody>
            </table>
        </div>
    </div>
    """
    return render_base("Solicitações Resolvidas", content, session_data, message)

# ==========================================
# ========== PROCESSAMENTO DE ROTAS ========
# ==========================================

class RequestHandler(BaseHTTPRequestHandler):
    def redirect(self, location, cookie_header=None):
        self.send_response(303)
        self.send_header('Location', location)
        if cookie_header:
            self.send_header('Set-Cookie', cookie_header)
        self.end_headers()

    def get_session(self):
        cookie = SimpleCookie(self.headers.get('Cookie'))
        if 'session_id' in cookie:
            sid = cookie['session_id'].value
            return SESSIONS.get(sid)
        return None

    def parse_post_data(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        return urllib.parse.parse_qs(post_data)

    def do_GET(self):
        session_data = self.get_session()

        if not session_data and self.path != '/login':
            return self.redirect('/login')

        if self.path == '/login':
            if session_data:
                return self.redirect('/')
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(render_login().encode('utf-8'))
            return

        if self.path == '/logout':
            cookie = SimpleCookie(self.headers.get('Cookie'))
            if 'session_id' in cookie:
                SESSIONS.pop(cookie['session_id'].value, None)
            return self.redirect('/login', "session_id=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/")

        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)

        if self.path == '/':
            c.execute("SELECT * FROM solicitacao WHERE status NOT IN ('Resolvido', 'Improdutivo') ORDER BY id DESC")
            solicitacoes = c.fetchall()
            
            c.execute("SELECT status, COUNT(*) as qtd FROM solicitacao GROUP BY status")
            res_kpis = c.fetchall()
            kpis = {r['status']: r['qtd'] for r in res_kpis}
            
            # Adiciona contagem forçada de resolvidos no totalizador do painel
            c.execute("SELECT COUNT(*) as qtd FROM solicitacao WHERE status IN ('Resolvido', 'Improdutivo')")
            total_concluidos = c.fetchone()
            kpis['Resolvido'] = total_concluidos['qtd'] if total_concluidos else 0

            html = render_index(session_data, kpis, solicitacoes)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif self.path == '/resolvidos':
            c.execute("SELECT * FROM solicitacao WHERE status IN ('Resolvido', 'Improdutivo') ORDER BY id DESC")
            solicitacoes = c.fetchall()
            html = render_resolvidos(session_data, solicitacoes)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif self.path == '/alterar_senha':
            html = render_alterar_senha(session_data)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif self.path == '/usuarios' and session_data['role'] == 'admin':
            c.execute("SELECT id, username, senha, role FROM usuarios ORDER BY id ASC")
            users = c.fetchall()
            # Converte dicionários de volta para tuplas estruturadas apenas para o render_usuarios antigo ler sem quebras
            users_tuples = [(u['id'], u['username'], u['senha'], u['role']) for u in users]
            html = render_usuarios(session_data, users_tuples)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        elif self.path == '/logo.jpg':
            if os.path.exists("logo.jpg"):
                self.send_response(200)
                self.send_header('Content-type', 'image/jpeg')
                self.end_headers()
                with open("logo.jpg", "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)

        else:
            self.send_error(404)

        conn.close()

    def do_POST(self):
        session_data = self.get_session()
        parsed_data = self.parse_post_data()
        
        # Converte dicionário do parse para formato limpo de strings
        data = {k: v[0] for k, v in parsed_data.items()}

        if self.path == '/login':
            username_input = data.get('usuario', '').strip()
            senha_input = data.get('senha', '')
            
            conn = get_db_connection()
            c = conn.cursor(cursor_factory=RealDictCursor)
            c.execute("SELECT username, senha, role FROM usuarios WHERE username=%s", (username_input,))
            user = c.fetchone()
            conn.close()

            if user and user['senha'] == senha_input:
                sid = str(uuid.uuid4())
                SESSIONS[sid] = {'usuario': user['username'], 'role': user['role']}
                return self.redirect('/', f"session_id={sid}; Path=/; HttpOnly")
            else:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(render_login(message="Usuário ou senha inválidos!").encode('utf-8'))
                return

        if not session_data:
            return self.redirect('/login')

        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)

        if self.path == '/':
            id_editar = data.get('id_editar', '')
            if id_editar:
                c.execute("""UPDATE solicitacao 
                             SET cod_cliente=%s, cliente_razao=%s, equipamentos=%s, data=%s, contato=%s 
                             WHERE id=%s""",
                          (data['cod_cliente'], data['cliente_razao'], data['equipamentos'], data['data'], data['contato'], int(id_editar)))
            else:
                c.execute("""INSERT INTO solicitacao (cod_cliente, cliente_razao, equipamentos, data, contato, status, solicitante) 
                             VALUES (%s, %s, %s, %s, %s, 'Restabelecer', %s)""",
                          (data['cod_cliente'], data['cliente_razao'], data['equipamentos'], data['data'], data['contato'], session_data['usuario']))
            conn.commit()

        elif self.path == '/alterar_senha':
            c.execute("SELECT senha FROM usuarios WHERE username=%s", (session_data['usuario'],))
            user_pwd = c.fetchone()
            
            if not user_pwd or user_pwd['senha'] != data['senha_atual']:
                html = render_alterar_senha(session_data, message="Senha atual incorreta!", msg_type="danger")
            elif data['nova_senha'] != data['confirmar_senha']:
                html = render_alterar_senha(session_data, message="A nova senha e a confirmação não conferem!", msg_type="danger")
            else:
                c.execute("UPDATE usuarios SET senha=%s WHERE username=%s", (data['nova_senha'], session_data['usuario']))
                conn.commit()
                html = render_alterar_senha(session_data, message="Senha atualizada com sucesso!", msg_type="success")
                
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
            conn.close()
            return

        elif self.path == '/usuarios/salvar' and session_data['role'] == 'admin':
            id_user = data.get('id_usuario', '')
            if id_user:
                c.execute("UPDATE usuarios SET username=%s, senha=%s, role=%s WHERE id=%s",
                          (data['username'].strip(), data['senha'], data['role'], int(id_user)))
            else:
                c.execute("INSERT INTO usuarios (username, senha, role) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING",
                          (data['username'].strip(), data['senha'], data['role']))
            conn.commit()
            conn.close()
            return self.redirect('/usuarios')

        elif self.path == '/usuarios/deletar' and session_data['role'] == 'admin':
            c.execute("DELETE FROM usuarios WHERE id=%s", (int(data['id']),))
            conn.commit()
            conn.close()
            return self.redirect('/usuarios')

        elif self.path == '/atualizar_status' and session_data['role'] == 'admin':
            status = data.get('status', 'Restabelecer')
            if data.get('btn_resolver') == 'Resolvido':
                status = 'Resolvido'
                
            obs = data.get('obs_improdutivo', '') if status == 'Improdutivo' else ''
            
            if status in ['Resolvido', 'Improdutivo']:
                c.execute("UPDATE solicitacao SET status=%s, obs_improdutivo=%s, resolvido_por=%s WHERE id=%s", 
                          (status, obs, session_data['usuario'], int(data['id'])))
            else:
                c.execute("UPDATE solicitacao SET status=%s, obs_improdutivo=%s, resolvido_por=NULL WHERE id=%s", 
                          (status, obs, int(data['id'])))
            conn.commit()

        elif self.path == '/retroceder' and session_data['role'] == 'admin':
            c.execute("UPDATE solicitacao SET status='Restabelecer', resolvido_por=NULL WHERE id=%s", (int(data['id']),))
            conn.commit()

        elif self.path == '/deletar':
            c.execute("DELETE FROM solicitacao WHERE id=%s", (int(data['id']),))
            conn.commit()

        conn.close()
        return self.redirect('/')

if __name__ == '__main__':
    if not os.path.exists("logo.jpg"):
        print("AVISO: Lembre-se de salvar sua logo como 'logo.jpg' na mesma pasta deste script para exibição no sistema!")
        
    porta = int(os.environ.get("PORT", 5000))
    
    server = ThreadedHTTPServer(('', porta), RequestHandler)
    print("========================================")
    print(f"Controle do KPAX Iniciado na porta {porta}!")
    print("========================================")
    print("Controle do KPAX Iniciado com Sucesso!")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")