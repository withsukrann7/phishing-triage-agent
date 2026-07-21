import re

def clean_text(text):
    """
    E-posta gövdesindeki URL'leri sabit bir token'a çevirir
    ve metni makine öğrenmesi modeline hazır hale getirir.
    """
    if not isinstance(text, str):  #amacımız error handling , sonraki satırlarda str fonksiyonların çalışması için şart .
        return "" #metin değilse geriye boş string döndürür.
    
    text = text.lower() #hepsinini küçük harfe çevirip kelime kümesini standartlaştırırız.
    #ML ve TF-IDF için önemlidir.

    # URL'leri tespit edip 'URLTOKEN' yapıyoruz (Overfitting'i önlemek için)
    text = re.sub(r"http\S+|www\.\S+", " URLTOKEN ", text) 

    # E-posta adreslerini maskeliyoruz
    text = re.sub(r"\S+@\S+", " EMAILTOKEN ", text)

    # Harf ve sayı dışındaki özel karakterleri temizliyoruz
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)

    # Fazla boşlukları tek boşluğa indiriyoruz
    text = re.sub(r"\s+", " ", text).strip()
    #strip() metnin en başındaki ve en sonundaki lüzumsuz boşlukları kırpar.
    
    return text

    """
    re.sub()----> re.sub() (Substitute) karmaşık Regex kalıplarını bulup başka bir metinle (örneğin URLTOKEN) değiştirmeye yarar
    .strip() ---->temizlenen metnin sadece en başındaki ve en sonundaki lüzumsuz boşlukları kırpar.
    """
