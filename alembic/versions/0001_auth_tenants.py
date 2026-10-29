"""auth and tenants with PostgreSQL RLS"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_auth_tenants'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    is_pg = bind.dialect.name == 'postgresql'
    if is_pg:
        op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
        op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')
        uuid_type = postgresql.UUID(as_uuid=True)
        now = sa.text('now()')
        tenant_id_default = sa.text('gen_random_uuid()')
        email_type = postgresql.CITEXT()
    else:
        uuid_type = sa.String(36)
        now = sa.text('CURRENT_TIMESTAMP')
        tenant_id_default = None
        email_type = sa.String(320)
    op.create_table('tenants', sa.Column('id', uuid_type, primary_key=True, server_default=tenant_id_default), sa.Column('name', sa.Text(), nullable=False), sa.Column('slug', sa.String(120), nullable=False, unique=True), sa.Column('plan', sa.String(40), nullable=False, server_default='pilot'), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=now), sa.Column('deleted_at', sa.DateTime(timezone=True)))
    op.create_table('users', sa.Column('id', uuid_type, primary_key=True, server_default=tenant_id_default), sa.Column('tenant_id', uuid_type, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False), sa.Column('email', email_type, nullable=False), sa.Column('full_name', sa.Text()), sa.Column('role', sa.String(20), nullable=False, server_default='manager'), sa.Column('manager_id', uuid_type, sa.ForeignKey('users.id')), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=now), sa.Column('last_login_at', sa.DateTime(timezone=True)), sa.Column('deleted_at', sa.DateTime(timezone=True)), sa.UniqueConstraint('tenant_id','email',name='uq_users_tenant_email'))
    if is_pg: op.create_check_constraint('ck_users_role', 'users', "role IN ('owner','rop','manager','analyst')")
    op.create_table('magic_link_tokens', sa.Column('id', uuid_type, primary_key=True, server_default=tenant_id_default), sa.Column('user_id', uuid_type, sa.ForeignKey('users.id', ondelete='CASCADE')), sa.Column('tenant_id', uuid_type, sa.ForeignKey('tenants.id', ondelete='CASCADE')), sa.Column('email', email_type, nullable=False), sa.Column('token_hash', sa.String(64), nullable=False), sa.Column('purpose', sa.String(10), nullable=False), sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False), sa.Column('used_at', sa.DateTime(timezone=True)), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=now))
    op.create_index('idx_magic_link_tokens_hash','magic_link_tokens',['token_hash'])
    op.create_table('sessions', sa.Column('id', uuid_type, primary_key=True, server_default=tenant_id_default), sa.Column('user_id', uuid_type, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False), sa.Column('tenant_id', uuid_type, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False), sa.Column('token_hash', sa.String(64), nullable=False, unique=True), sa.Column('user_agent', sa.Text()), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=now), sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False), sa.Column('revoked_at', sa.DateTime(timezone=True)))
    op.create_index('idx_sessions_hash','sessions',['token_hash'])
    if is_pg:
        op.execute('ALTER TABLE users ENABLE ROW LEVEL SECURITY')
        op.execute("CREATE POLICY users_tenant_isolation ON users USING (tenant_id = current_setting('app.current_tenant', true)::uuid)")


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('DROP POLICY IF EXISTS users_tenant_isolation ON users')
    op.drop_index('idx_sessions_hash', table_name='sessions'); op.drop_table('sessions')
    op.drop_index('idx_magic_link_tokens_hash', table_name='magic_link_tokens'); op.drop_table('magic_link_tokens')
    op.drop_table('users'); op.drop_table('tenants')
