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
