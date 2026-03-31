# Pão 54 - Plataforma de Gestão para Micropadaria

Agora o projeto possui uma versão pronta para rodar **online no Streamlit Cloud**, sem necessidade de instalar programas localmente.

## Opção recomendada: rodar online no Streamlit Community Cloud

### 1) Suba este projeto para um repositório no GitHub
- Crie um repositório no GitHub (público ou privado).
- Envie os arquivos desta pasta para lá.

### 2) Publique no Streamlit Cloud
1. Acesse: https://share.streamlit.io/
2. Clique em **New app**.
3. Selecione seu repositório.
4. Em **Main file path**, informe: `streamlit_app.py`.
5. Clique em **Deploy**.

Pronto: sua plataforma ficará acessível via link web.

---

## Erro de acesso: “You do not have access to this app or it does not exist”

Se aparecer esta mensagem, quase sempre é configuração de acesso no Streamlit Cloud (não é erro do código).

### Como corrigir (passo a passo)
1. Entre no Streamlit Cloud com a **mesma conta GitHub dona do repositório** usado no deploy.
2. Abra o app no painel do Streamlit e vá em **Settings → Sharing**.
3. Em **Who can view this app**, escolha:
   - **Public** (recomendado para testes rápidos), ou
   - **Only invited users** e adicione explicitamente os e-mails permitidos.
4. Se o repositório for privado, confirme em **Settings → Linked GitHub account** se a conta conectada é a correta.
5. No GitHub, valide se você tem acesso ao repo/organização.
6. Faça **Reboot app** no menu do Streamlit para forçar nova sessão.

### Checklist rápido
- Você está logado no Streamlit com a conta correta?
- A conta logada tem acesso ao repositório do GitHub?
- O app está público ou seu e-mail foi convidado?
- O link acessado é o mesmo app atualmente publicado?

---

## Credenciais iniciais da aplicação Pão 54

Estas credenciais são da **tela de login interna do sistema**, e só funcionam depois que o acesso ao app no Streamlit Cloud já estiver liberado.
## Credenciais iniciais

- Email: `admin@pao54.local`
- Senha: `pao54admin`

> Troque a senha em produção.

---

## Funcionalidades entregues (na versão Streamlit)

- Login e senha para usuários cadastrados.
- Dashboard com indicadores principais.
- Cadastro de receitas com escala de produção e impressão (via navegador).
- Agenda de encomendas.
- Controle financeiro (entradas/saídas).
- Registro de estoque com alerta de reposição.
- Cadastro de produtos com preço, custo e margem.

---

## Arquivo principal para deploy online

- `streamlit_app.py`

---

## Se quiser manter também a versão Flask

A versão em Flask permanece no arquivo `app.py`, mas para o seu cenário (sem instalação local), use o Streamlit Cloud com `streamlit_app.py`.


## Atualizações recentes
- Receitas com ingredientes selecionados exclusivamente do estoque, quantidade/unidade separadas e recálculo automático de custo da receita.
- Encomendas com cadastro de clientes, histórico por cliente e edição/exclusão individual dos pedidos.
- Produtos com histórico de preços por data/local, incluindo marca e especificação da embalagem.
