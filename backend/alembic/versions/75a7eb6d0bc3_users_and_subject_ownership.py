"""users and subject ownership

Adds accounts and makes every subject belong to one.

Autogenerate wanted to add subject_profiles.user_id as NOT NULL in a single
step, which fails against existing rows. This instead seeds an admin account,
hands it everything that already exists, and only then makes the column
required — so the app's pre-auth data survives the upgrade.

The seeded account has a deliberately unusable password hash. Set a real
password before logging in; bcrypt rejects '!' as a malformed hash, so no
password can match it in the meantime.

Revision ID: 75a7eb6d0bc3
Revises: 0540f2dffab9
Create Date: 2026-10-04 21:47:22.032701
"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa


revision: str = '75a7eb6d0bc3'
down_revision: Union[str, None] = '0540f2dffab9'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

# Overridable so a fresh deployment can seed a different owner
SEED_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "joelallenc03@gmail.com")
SEED_NAME = os.getenv("SEED_ADMIN_NAME", "Joel")
UNUSABLE_PASSWORD_HASH = "!"


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    connection = op.get_bind()

    # Seed the admin only if there are subjects to hand over, so a brand new
    # database doesn't get a phantom account it never asked for.
    existing_profiles = connection.execute(
        sa.text("SELECT COUNT(*) FROM subject_profiles")
    ).scalar()

    op.add_column('subject_profiles', sa.Column('user_id', sa.Integer(), nullable=True))

    if existing_profiles:
        owner_id = connection.execute(
            sa.text(
                "INSERT INTO users (email, display_name, password_hash, is_admin, is_active) "
                "VALUES (:email, :name, :pw, true, true) RETURNING id"
            ),
            {"email": SEED_EMAIL, "name": SEED_NAME, "pw": UNUSABLE_PASSWORD_HASH},
        ).scalar()

        connection.execute(
            sa.text("UPDATE subject_profiles SET user_id = :owner WHERE user_id IS NULL"),
            {"owner": owner_id},
        )

    op.alter_column('subject_profiles', 'user_id', nullable=False)
    op.create_index(
        op.f('ix_subject_profiles_user_id'), 'subject_profiles', ['user_id'], unique=False
    )
    op.create_foreign_key(
        'fk_subject_profiles_user_id', 'subject_profiles', 'users', ['user_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_subject_profiles_user_id', 'subject_profiles', type_='foreignkey')
    op.drop_index(op.f('ix_subject_profiles_user_id'), table_name='subject_profiles')
    op.drop_column('subject_profiles', 'user_id')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
