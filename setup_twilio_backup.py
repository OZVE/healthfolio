#!/usr/bin/env python3
"""
Script de configuración rápida para Twilio WhatsApp como backup
Soluciona el problema de Evolution API suspendida
"""

import os
import requests
from dotenv import load_dotenv

def setup_twilio_backup():
    print("🚀 Configurando Twilio WhatsApp como backup...")
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Verificar si ya está configurado
    if os.getenv('TWILIO_ACCOUNT_SID') and os.getenv('TWILIO_AUTH_TOKEN'):
        print("✅ Twilio ya está configurado")
        return True
    
    print("\n📋 INSTRUCCIONES PARA CONFIGURAR TWILIO:")
    print("=" * 50)
    
    print("\n1️⃣ CREAR CUENTA TWILIO:")
    print("   🔗 https://console.twilio.com/")
    print("   📝 Registrarse (gratis)")
    
    print("\n2️⃣ OBTENER CREDENCIALES:")
    print("   📍 Dashboard → Account Info")
    print("   📋 Account SID: ACxxxxx...")
    print("   🔑 Auth Token: [tu_token]")
    
    print("\n3️⃣ CONFIGURAR WHATSAPP SANDBOX:")
    print("   🔗 https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
    print("   📱 Número: +1 415 523 8886")
    print("   💬 Código: join [tu-codigo-unico]")
    
    print("\n4️⃣ AGREGAR VARIABLES EN RAILWAY:")
    print("   🚂 Railway → Variables → + New Variable")
    print("   📝 Agregar estas variables:")
    
    variables = {
        'WHATSAPP_PROVIDER': 'twilio',
        'TWILIO_ACCOUNT_SID': 'ACxxxxx...',
        'TWILIO_AUTH_TOKEN': '[tu_token]',
        'TWILIO_WHATSAPP_NUMBER': 'whatsapp:+14155238886'
    }
    
    for key, value in variables.items():
        print(f"   • {key}: {value}")
    
    print("\n5️⃣ CONFIGURAR WEBHOOK:")
    print("   🔗 https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
    print("   📡 URL: https://healthfolio-production.up.railway.app/webhook/twilio")
    
    print("\n6️⃣ PROBAR:")
    print("   📱 Envía mensaje a +1 415 523 8886")
    print("   💬 Escribe: join [tu-codigo-unico]")
    
    print("\n" + "=" * 50)
    print("🎯 DESPUÉS DE CONFIGURAR, EL BOT FUNCIONARÁ AUTOMÁTICAMENTE")
    print("🔄 Si Evolution API se recupera, puedes cambiar WHATSAPP_PROVIDER=evolution")

def test_evolution_status():
    """Verifica el estado de Evolution API"""
    print("\n🔍 Verificando estado de Evolution API...")
    
    try:
        # URL desde el dashboard
        url = "https://socialapp-evolution-api.ynuqry.easypanel.host"
        response = requests.get(f"{url}/manager", timeout=10)
        
        if response.status_code == 200:
            print("✅ Evolution API está funcionando")
            return True
        else:
            print(f"❌ Evolution API error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Evolution API no disponible: {str(e)}")
        return False

def main():
    print("🐳 HEALTFOLIO - SOLUCIÓN DE PROBLEMAS DE WHATSAPP")
    print("=" * 60)
    
    # Verificar Evolution API
    evolution_ok = test_evolution_status()
    
    if not evolution_ok:
        print("\n🚨 EVOLUTION API NO DISPONIBLE")
        print("📋 Configurando Twilio como backup...")
        setup_twilio_backup()
    else:
        print("\n✅ EVOLUTION API FUNCIONANDO")
        print("💡 Si sigues teniendo problemas, reinicia la instancia desde el dashboard")

if __name__ == "__main__":
    main()
