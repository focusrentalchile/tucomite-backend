"""Default branded HTML email templates for onboarding invites."""

from app.domain.email_templates import (
    TEMPLATE_ADMINISTRATOR_INVITE,
    TEMPLATE_CARETAKER_INVITE,
    TEMPLATE_CLIENT_ACTIVATION,
    TEMPLATE_CLIENT_WELCOME,
    TEMPLATE_COMMITTEE_INVITE,
    TEMPLATE_RESIDENT_INVITE,
)


def _shell(*, title: str, inner: str) -> str:
    """Wrap body content in a professional TuComité email chrome with logo."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#eef2f8;font-family:Arial,Helvetica,sans-serif;color:#001545;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef2f8;padding:28px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border:1px solid #d5deee;border-radius:18px;overflow:hidden;box-shadow:0 8px 24px rgba(0,21,69,0.08);">
          <tr>
            <td style="padding:26px 28px 18px;background:linear-gradient(135deg,#001545 0%,#0b2f7a 100%);text-align:center;">
              <img src="{{{{logo_url}}}}" alt="TuComité" width="168" style="display:block;margin:0 auto 10px;max-width:168px;height:auto;border:0;" />
              <div style="font-size:13px;letter-spacing:0.04em;color:rgba(255,255,255,0.86);">Tu comunidad, mejor conectada</div>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 28px 10px;">
              {inner}
            </td>
          </tr>
          <tr>
            <td style="padding:8px 28px 28px;">
              <p style="margin:0 0 6px;font-size:15px;line-height:1.5;color:#001545;"><strong>Equipo TuComité</strong></p>
              <p style="margin:0 0 4px;font-size:14px;line-height:1.45;"><a href="{{{{site_url}}}}" style="color:#1554d1;text-decoration:none;">tucomite.cl</a></p>
              <p style="margin:10px 0 0;font-size:13px;line-height:1.4;color:#5a6a8a;font-style:italic;">Comunidades mejor conectadas.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    TEMPLATE_CLIENT_ACTIVATION: {
        "name": "Activación de cuenta",
        "subject": "Activa tu cuenta en TuComité",
        "html_body": _shell(
            title="Activación de cuenta",
            inner="""
              <p style="margin:0 0 16px;font-size:16px;line-height:1.55;">Hola, {{name}}:</p>
              <p style="margin:0 0 14px;font-size:20px;line-height:1.35;font-weight:700;color:#001545;">¡Bienvenido a TuComité!</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Recibimos el registro de <strong>{{building_name}}</strong>. Para comenzar, activá tu cuenta con el botón de abajo.</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Correo de acceso: <strong>{{email}}</strong></p>
              <p style="margin:28px 0;text-align:center;">
                <a href="{{invite_url}}" style="display:inline-block;padding:14px 28px;border-radius:999px;background:#1554d1;color:#ffffff;font-size:16px;font-weight:700;text-decoration:none;">Activar cuenta</a>
              </p>
              <p style="margin:0 0 14px;font-size:14px;line-height:1.55;color:#5a6a8a;">Si el botón no funciona, abrí este enlace:<br />
              <a href="{{invite_url}}" style="color:#1554d1;word-break:break-all;">{{invite_url}}</a></p>
              <p style="margin:0;font-size:15px;line-height:1.6;">Después de activar, vas a ingresar al panel de TuComité.</p>
            """,
        ),
    },
    TEMPLATE_CLIENT_WELCOME: {
        "name": "Bienvenida cliente",
        "subject": "¡Bienvenido a TuComité! Tu comunidad comienza una nueva etapa",
        "html_body": _shell(
            title="Bienvenida cliente",
            inner="""
              <p style="margin:0 0 16px;font-size:16px;line-height:1.55;">Hola, {{name}}:</p>
              <p style="margin:0 0 14px;font-size:20px;line-height:1.35;font-weight:700;color:#001545;">¡Bienvenido a TuComité!</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Nos alegra que tu comunidad sea parte de esta nueva forma de organizar, comunicar y gestionar las decisiones de su edificio.</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Sabemos que liderar un comité implica tiempo, compromiso y muchas conversaciones. Por eso creamos <strong>TuComité.cl</strong>, una plataforma diseñada para ayudarte a transformar esas conversaciones en decisiones claras, organizadas y con seguimiento.</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;"><strong>Como presidente del comité, serás quien dé el primer paso.</strong></p>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>Tus datos de acceso:</strong></p>
              <ul style="margin:0 0 18px;padding-left:20px;font-size:15px;line-height:1.65;">
                <li>Correo: <strong>{{email}}</strong></li>
                <li>Clave temporal: <strong>{{password}}</strong></li>
              </ul>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>Para comenzar:</strong></p>
              <ol style="margin:0 0 18px;padding-left:20px;font-size:15px;line-height:1.65;">
                <li>Ingresá a <a href="{{invite_url}}" style="color:#1554d1;">TuComité</a> con el correo y la clave de arriba.</li>
                <li>Configurá el perfil de tu edificio.</li>
                <li>Invitá a los demás integrantes del comité: en configuración, usuarios y el botón +Agregar.</li>
                <li>Incorporá al administrador y al mayordomo, si corresponde.</li>
                <li>Creá el primer tema que quieran gestionar como comunidad.</li>
              </ol>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>¿Qué podrán hacer desde ahora?</strong></p>
              <ul style="margin:0 0 18px;padding-left:20px;font-size:15px;line-height:1.65;">
                <li>Organizar los temas importantes del edificio.</li>
                <li>Participar en votaciones y registrar decisiones.</li>
                <li>Consultar los acuerdos y su historial.</li>
                <li>Dar seguimiento al avance de los asuntos del comité.</li>
              </ul>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;"><strong>Tu opinión también construye TuComité.</strong></p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Estás participando en nuestras primeras experiencias con comunidades reales. Queremos escucharte, acompañarte y mejorar la herramienta junto a ustedes.</p>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;">¿Necesitas ayuda para comenzar?</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Solicita una video llamada con nuestro equipo:<br />
              <a href="mailto:hola@tucomite.cl" style="color:#1554d1;">hola@tucomite.cl</a><br />
              +56 9 5801 6449</p>
              <p style="margin:0;font-size:15px;line-height:1.6;"><strong>Bienvenido a una gestión más simple, conectada y organizada.</strong></p>
            """,
        ),
    },
    TEMPLATE_COMMITTEE_INVITE: {
        "name": "Invitación comité",
        "subject": "¡Tu comunidad tiene una nueva forma de trabajar en equipo!",
        "html_body": _shell(
            title="Invitación comité",
            inner="""
              <p style="margin:0 0 16px;font-size:16px;line-height:1.55;">Hola, {{name}}:</p>
              <p style="margin:0 0 14px;font-size:20px;line-height:1.35;font-weight:700;color:#001545;">¡Tu comunidad tiene una nueva forma de trabajar en equipo!</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Has sido invitado a formar parte del espacio digital de <strong>{{building_name}}</strong> en TuComité.cl.</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Una plataforma creada para que los integrantes del comité puedan comunicarse mejor, organizar los temas importantes y tomar decisiones de manera más clara y ordenada.</p>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>¿Qué podrás hacer en TuComité?</strong></p>
              <ul style="margin:0 0 18px;padding-left:20px;font-size:15px;line-height:1.65;">
                <li>Conocer los temas que están siendo tratados.</li>
                <li>Compartir tus opiniones y comentarios.</li>
                <li>Participar en las votaciones del comité.</li>
                <li>Revisar acuerdos y decisiones anteriores.</li>
                <li>Consultar el estado de los asuntos en desarrollo.</li>
              </ul>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>¿Cómo comenzar?</strong></p>
              <ol style="margin:0 0 18px;padding-left:20px;font-size:15px;line-height:1.65;">
                <li>Ingresa desde tu invitación: <a href="{{invite_url}}" style="color:#1554d1;">enlace de acceso</a>.</li>
                <li>Activa tu cuenta.</li>
                <li>Explora los temas de tu edificio.</li>
                <li>¡Comienza a participar!</li>
              </ol>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;"><strong>Menos mensajes perdidos. Más decisiones claras.</strong></p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Estamos comenzando esta experiencia con comunidades reales, por lo que tus sugerencias serán muy valiosas para seguir mejorando.</p>
              <p style="margin:0;font-size:15px;line-height:1.6;">¿Tienes dudas? Escríbenos:<br />
              <a href="mailto:hola@tucomite.cl" style="color:#1554d1;">hola@tucomite.cl</a><br />
              +56 9 5801 6449</p>
            """,
        ),
    },
    TEMPLATE_ADMINISTRATOR_INVITE: {
        "name": "Invitación administrador",
        "subject": "¡Bienvenido a TuComité!",
        "html_body": _shell(
            title="Invitación administrador",
            inner="""
              <p style="margin:0 0 16px;font-size:16px;line-height:1.55;">Hola, {{name}}:</p>
              <p style="margin:0 0 14px;font-size:20px;line-height:1.35;font-weight:700;color:#001545;">¡Bienvenido a TuComité!</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">El comité de <strong>{{building_name}}</strong> te ha invitado a participar en su nuevo espacio de gestión digital.</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Sabemos que una buena administración necesita comunicación clara, coordinación y seguimiento. Por eso desarrollamos TuComité, una herramienta que facilita el trabajo conjunto entre la administración y el comité.</p>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>¿Qué buscamos mejorar?</strong></p>
              <ul style="margin:0 0 18px;padding-left:20px;font-size:15px;line-height:1.65;">
                <li>Centralizar los asuntos relevantes de la comunidad.</li>
                <li>Facilitar la comunicación con el comité.</li>
                <li>Mantener un registro organizado de decisiones y acuerdos.</li>
                <li>Mejorar el seguimiento de los temas pendientes.</li>
                <li>Reducir la pérdida de información entre mensajes y conversaciones.</li>
              </ul>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>Para comenzar:</strong></p>
              <ol style="margin:0 0 18px;padding-left:20px;font-size:15px;line-height:1.65;">
                <li>Accede desde <a href="{{invite_url}}" style="color:#1554d1;">enlace de invitación</a>.</li>
                <li>Activa tu cuenta de administrador.</li>
                <li>Revisa la información disponible de tu comunidad.</li>
                <li>Comienza a colaborar con el comité según los permisos habilitados.</li>
              </ol>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;"><strong>Una comunidad mejor organizada también facilita tu trabajo.</strong></p>
              <p style="margin:0;font-size:15px;line-height:1.6;">Si tienes dudas o sugerencias, estaremos encantados de ayudarte.<br />
              <a href="mailto:hola@tucomite.cl" style="color:#1554d1;">hola@tucomite.cl</a><br />
              +56 9 5801 6449</p>
            """,
        ),
    },
    TEMPLATE_CARETAKER_INVITE: {
        "name": "Invitación mayordomo",
        "subject": "¡Te damos la bienvenida a TuComité!",
        "html_body": _shell(
            title="Invitación mayordomo",
            inner="""
              <p style="margin:0 0 16px;font-size:16px;line-height:1.55;">Hola, {{name}}:</p>
              <p style="margin:0 0 14px;font-size:20px;line-height:1.35;font-weight:700;color:#001545;">¡Te damos la bienvenida a TuComité!</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">El comité de <strong>{{building_name}}</strong> te ha invitado a participar en una nueva herramienta que busca facilitar la comunicación y organización de nuestra comunidad.</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Sabemos que tu trabajo es fundamental para el funcionamiento diario del edificio. Por eso queremos que también formes parte de este espacio.</p>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>¿Para qué te servirá TuComité?</strong></p>
              <ul style="margin:0 0 18px;padding-left:20px;font-size:15px;line-height:1.65;">
                <li>Conocer los asuntos del edificio que requieran tu participación.</li>
                <li>Mantener una comunicación más organizada.</li>
                <li>Consultar la información compartida contigo.</li>
                <li>Apoyar el seguimiento de las actividades que te correspondan.</li>
              </ul>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>Comenzar es muy sencillo:</strong></p>
              <ol style="margin:0 0 18px;padding-left:20px;font-size:15px;line-height:1.65;">
                <li>Ingresa desde <a href="{{invite_url}}" style="color:#1554d1;">enlace de invitación</a>.</li>
                <li>Activa tu cuenta.</li>
                <li>Revisa la información disponible para tu perfil.</li>
              </ol>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Nuestro objetivo es facilitar el trabajo de todos, evitando confusiones y mejorando la coordinación.</p>
              <p style="margin:0;font-size:15px;line-height:1.6;">Si tienes dudas o sugerencias, estaremos encantados de ayudarte.<br />
              <a href="mailto:hola@tucomite.cl" style="color:#1554d1;">hola@tucomite.cl</a><br />
              +56 9 5801 6449</p>
            """,
        ),
    },
    TEMPLATE_RESIDENT_INVITE: {
        "name": "Invitación residente",
        "subject": "¡Tenemos novedades para tu comunidad!",
        "html_body": _shell(
            title="Invitación residente",
            inner="""
              <p style="margin:0 0 16px;font-size:16px;line-height:1.55;">Hola, {{name}}:</p>
              <p style="margin:0 0 14px;font-size:20px;line-height:1.35;font-weight:700;color:#001545;">¡Tenemos novedades para tu comunidad!</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">En <strong>{{building_name}}</strong> estamos comenzando a utilizar TuComité.cl, una plataforma digital creada para mejorar la organización y la comunicación entre quienes trabajan por el bienestar de nuestro edificio.</p>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>¿Qué es TuComité?</strong></p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Es una herramienta que ayuda al comité y a la administración a organizar los temas importantes, gestionar decisiones y mantener un mejor seguimiento de los acuerdos.</p>
              <p style="margin:0 0 8px;font-size:15px;line-height:1.6;"><strong>¿Qué significa esto para ti?</strong></p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">Una comunidad que puede trabajar de manera más organizada, con mejor comunicación y mayor claridad sobre los asuntos que se gestionan.</p>
              <p style="margin:0 0 14px;font-size:15px;line-height:1.6;">TuComité está creciendo y, progresivamente, incorporaremos nuevas funciones y beneficios pensados también para los residentes.</p>
              <p style="margin:0 0 18px;font-size:15px;line-height:1.6;"><strong>Conoce más sobre esta iniciativa:</strong><br />
              <a href="{{site_url}}" style="display:inline-block;margin-top:10px;padding:12px 20px;background:#1554d1;color:#ffffff;text-decoration:none;border-radius:10px;font-weight:700;">Visitar TuComité.cl</a></p>
              <p style="margin:0;font-size:15px;line-height:1.6;">Estamos construyendo una mejor experiencia para vivir en comunidad.<br />¡Bienvenido a esta nueva etapa!</p>
            """,
        ),
    },
}
