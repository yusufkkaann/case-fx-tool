# tool.py İncelemesi

İncelemeyi, kodu okuyarak ve servisi farklı girdilerle **çalıştırarak** yaptım.
Python'a yeniyim; o yüzden dil/stil detaylarına değil, servisin bir **müşteriye**
ne yaptığına odaklandım: çağırıp dönen cevaplara baktım. Bulgular, müşteriye en
çok zarar veren en üstte olacak şekilde sıralı.

## 1. Hata olunca HTTP 200 ile uydurma bir `0` dönüyor (en tehlikelisi)

Koddaki `try/except`, her türlü hatayı yakalayıp `rate: 0.0, result: 0.0`
değerini **200 OK** ile döndürüyor. Yani upstream çökerse ya da bozuk cevap
verirse, çağıran (bir AI agent) hata olduğunu anlamıyor; kendinden emin, düzgün
görünen bir cevap görüp müşteriye **250 EUR = 0 TRY** diyor. Sessiz ve yanlış bir
sayı, görünür bir hatadan çok daha kötü.

*Nasıl doğrularım:* `FX_UPSTREAM_BASE`'i kapalı bir porta yönlendirip endpoint'i
çağırdım; `200` ve `result: 0.0` döndüğünü gördüm.

## 2. Kur, ait olmadığı bir güne aitmiş gibi gösteriliyor

Çalıştırınca iki şey fark ettim:

- Aynı para çifti için **iki farklı tarih** sorduğumda **aynı** kuru döndü. Demek
  ki cache tarihi hiç dikkate almıyor; ilk gelen kuru sonraki farklı tarihler için
  de veriyor.
- `rate_date` her zaman benim **sorduğum** tarihi yazıyor, kurun gerçekte ait
  olduğu tarihi değil. Bir hafta sonu tarihi sorduğumda bile, ECB o gün kur
  yayınlamamış olmasına rağmen `rate_date`'e o hafta sonu gününü yazdı.

Sonuç: müşteriye, aslında başka bir güne ait olan bir sayı, farklı bir tarihle
sunuluyor.

*Nasıl doğrularım:* iki farklı tarihle çağırıp aynı kuru aldım; bir Cumartesi
tarihiyle çağırıp `rate_date`'in Cumartesi çıktığını gördüm.

## 3. Kur 2 ondalığa yuvarlanıyor

Kod, çarpmadan önce `round(rate, 2)` yapıyor; `47.1234` gibi bir kur `47.12`
oluyor. Küçük tutarda fark etmez ama büyük bir işlemde bu, müşteri için gerçek
para kaybı demek.

*Nasıl doğrularım:* büyük bir tutar çevirip sonucu, tam (yuvarlanmamış) kurla
elde yaptığım çarpımla karşılaştırdım; tutmadı.

## Bu gece göndermeden önce düzelteceğim tek şey

**#1.** Diğerleri belirli durumlarda yanlış sayı üretiyor; ama #1 **her** upstream
aksaklığında, görünmeden ve üstüne "başarılı" (200) diyerek yanlış sayı üretiyor.
Geçici bir kesintiyi, müşteriye söylenen kendinden emin bir yanlışa çeviriyor.
Önce bunu düzeltirdim: hata olunca `200` + `0` yerine net bir hata kodu dönmeli.

## Daha düşük öncelikli ama fark ettiklerim

- **Zaman aşımı (timeout) yok.** Upstream'i yavaş/cevapsız bir adrese
  yönlendirdiğimde istek uzun süre asılı kaldı, dönmedi. Yavaş bir upstream
  agent'ı kilitleyebilir.
- **Adres kodun içine sabit yazılmış ve parametre adları farklı.** `UPSTREAM`
  sabit olduğu için `FX_UPSTREAM_BASE` okunmuyor. Ayrıca uç nokta `from`/`date`
  yerine `from_`/`on` kullanıyor; dokümandaki `?from=EUR&to=TRY&date=...` URL'ini
  aynen çağırdığımda `from` ve `date` beklediğim gibi çalışmadı. *Doğrulama:*
  dokümandaki URL'i çağırıp tarihin dikkate alınmadığını gördüm.

## Şüpheli görünüp de sorun çıkmadığına karar verdiğim şeyler

Python'a yeni olduğum için birkaç şeyi "acaba sorun mu?" diye işaretleyip sonra
okuyup/çalıştırıp karar verdim:

- Kodun üstünde tek bir yerde tutulan `_cache` (global bir sözlük) ilk başta
  gözüme takıldı. Ama bu servis tek bir süreçte çalışıyor ve çalışırken beklediğim
  gibi davrandı; burada bir sorun görmedim. Çok yüksek yük altındaki davranışını
  yine de daha deneyimli biriyle teyit etmek isterdim.
- Her yerde `async`/`await` kullanılması ilk bakışta gereksiz karmaşık geldi;
  araştırınca bunun FastAPI'nin normal çalışma biçimi olduğunu, bir kusur
  olmadığını gördüm.
