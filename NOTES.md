# Notlar

## Kararlar

- **Yanlış bir sayı, hiç sayı olmamasından kötüdür.** Bir yerde sorun olursa
  (upstream çöktü, cevap bozuk, zaman aşımı, girdi hatalı) servis uydurma bir kur
  ya da `0` dönmüyor; net bir hata kodu ve mesaj dönüyor. Çünkü bu sayıyı çağıran
  bir AI, ödeme yapan bir müşteriye söyleyecek.

- **Sorulan günde kur yoksa (hafta sonu/tatil), en yakın önceki günün kurunu
  dönüyoruz ama bunu açıkça belirtiyoruz.** `asked_date` benim sorduğum gün,
  `rate_date` ise kurun gerçekte ait olduğu gün. İkisi farklıysa model, müşteriye
  "bu sayı şu güne ait" diyebiliyor. Bunu, Google'da hafta sonu döviz sorunca
  "kur yok" demeyip Cuma'nın kurunu göstermesine benzettim: yardımcı ol ama hangi
  güne ait olduğunu gizleme.

- **Gelecek tarih ve 1999 öncesi tarih hata veriyor**, çünkü öyle bir kur yok;
  orada bir sayı dönmek uydurmak olurdu.

- **Bazı kontrolleri upstream'e gitmeden yapıyoruz** (tutar, aynı para birimi,
  tarih, para biriminin gerçekten var olup olmadığı). Çünkü Frankfurter bu
  hataların hepsine aynı "bulunamadı" cevabını veriyor; kendimiz kontrol edince
  müşteriye çok daha net bir hata mesajı verebiliyoruz.

- **Parayı `float` yerine `Decimal` ile tutuyoruz.** AI ilk sürümü `float` ile
  yazmıştı. Araştırınca `float`'ın para hesabında küçük yuvarlama hataları
  yaptığını (bilgisayarlarda `0.1 + 0.2` bile tam `0.3` etmiyor), finans işlerinde
  `Decimal` kullanmanın doğru yol olduğunu gördüm ve değiştirdim. Bunu koruyan bir
  test de ekledik: `2.675` sonucu `2.68` olmalı; `float` ile yanlışlıkla `2.67`
  çıkıyordu.

- **Aynı soru tekrar sorulunca upstream'e gitmiyoruz** (basit bir önbellek).
  Geçmiş bir tarihin kuru hiç değişmez, o yüzden süresiz saklanabiliyor; "en
  güncel" kur ise kısa bir süre saklanıyor.

## Sıradaki adımda ekleyebileceklerim

Bu görevi kasıtlı olarak küçük tuttum. Zamanım ve tecrübem arttıkça
ekleyeceklerim:

- Her para biriminin ondalık sayısı aynı değil (örneğin Japon Yeni'nde kuruş
  yok). Şu an hepsini 2 ondalık kabul ediyorum; bunu paraya göre ayarlamak
  isterdim.
- Basit bir loglama: bir sorun olduğunda "hangi istek gelmiş, ne olmuş" diye
  geriye bakabilmek için.
- Daha fazla test: gerçek API'nin cevabı değişirse bunu yakalayan bir test ve
  daha çok farklı girdiyle deneme.

## Kullandığım AI aracı

Daha önce hiç Python yazmadım. Bu yüzden Claude Code'u (Opus) bir mentor gibi
kullandım: kodu AI ile yazdım, sonra her parçayı bana açıklattırıp "burada neden
böyle, doğru yol bu mu" diye sordum ve öğrenerek ilerledim. Önemli kararları
(hafta sonu ne yapılacağı, hata mesajları, `Decimal`'e geçmek) kendim verdim. Kod
yazmadan önce de gerçek Frankfurter API'sini birkaç farklı istekle deneyip nasıl
davrandığını gördüm.

## Zorlandığım yer

TypeScript/Node.js geçmişim olduğu için katmanlı yapı, servis/istemci ayrımı
gibi kavramlar bana yabancı değildi. Asıl yeni olan Python'un kendisiydi:
dosyaları Python'da nasıl daha iyi ("Pythonic") düzenlerim (modül/paket yapısı,
`_` önekli yardımcılar, `@staticmethod` gibi konvansiyonlar) ve fonksiyon/tip
yazımına alışmak biraz vakit aldı; her tercihi "burada best practice ne" diye
sorarak öğrendim. Bir de ortam (venv) kaynaklı kafa karışıklığı yaşadım: editör
bir ara paketleri "bulunamadı" diye işaretledi, sonra bunun kodla değil, yanlış
Python sürümünün seçili olmasıyla ilgili olduğunu öğrendim. Buradan da Python'da
bir hatayla karşılaşınca önce "hangi ortam/sürüm çalışıyor" diye bakmayı öğrendim.

## AI'ın yanlış yaptığı bir şey

Servisi başlatan `run.sh` ve testleri çalıştıran `test.sh`, kurulum yaparken
bilgisayardaki Python'ı otomatik seçiyordu. Benim bilgisayarımda bu eski bir sürüm
(3.9) çıkıyordu ve **projeyi sıfırdan indirip** çalıştırdığımda testler hata verdi
— kodun kullandığı yeni Python yazımını eski sürüm anlamıyordu. Ben geliştirirken
bunu fark etmemiştim, çünkü kendi bilgisayarımda kurulumu elle doğru sürümle
yapmıştım; yani "bende çalışıyordu". Bunu, kendi kurulumuma güvenmek yerine tıpkı
sizin yapacağınız gibi **projeyi temiz bir kopyada** test ederek yakaladım.
Düzelttik: artık iki script de yeni Python sürümünü seçiyor, bulamazsa net bir
uyarı veriyor. Buradan çıkardığım ders: "bende çalışıyor" yetmez; karşı taraftaki
temiz kurulumda da çalıştığını görmek gerekiyor.
