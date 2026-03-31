# Pão 54 - Plataforma de Gestão para Micropadaria

Aplicação web para gestão diária da micropadaria **Pão 54**, com foco em produção, encomendas, financeiro, estoque e cadastro de produtos/custos.

## Funcionalidades implementadas

- Login e senha para acesso de usuários cadastrados.
- Dashboard com visão consolidada (receitas, encomendas, alertas de estoque e resumo financeiro).
- Cadastro de receitas com cálculo de escala para produção e impressão.
- Agenda de encomendas.
- Controle financeiro (entradas e saídas).
- Registro de estoque com alerta de reposição.
- Cadastro de produtos com preço e custo unitário para apoiar cálculo de margem.

## Stack

- **Backend:** Python + Flask
- **Banco de dados:** SQLite
- **Frontend:** HTML + CSS (paleta preta, dourada, branca e vermelha)

## Como executar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Acesse: `http://127.0.0.1:5000`

## Usuário inicial

- Email: `admin@pao54.local`
- Senha: `pao54admin`

> Recomendação: altere as credenciais em ambiente de produção.
