import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Checkbox, CircularProgress, Container, Divider, FormControlLabel, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { apiClient } from "../api/client";

const EMPTY = { gender: "", religion: "", denomination: "", city: "", employment_type: "", available_from: "", education: "", skills: "", employed_now: "", has_work_experience: "", health_status: "", had_surgery: "", smokes: "", work_history: [], education_history: [], training_history: [], references: [], dependents: [], accuracy_confirmed: false };
const OPTIONS = {
 gender: [["female","زن"],["male","مرد"]],
 employment_type: [["fulltime","تمام‌وقت"],["parttime","پاره‌وقت"],["project","پروژه‌ای / خارج شرکت"]],
 employed_now: [["yes","بله"],["no","خیر"]],
 has_work_experience: [["yes","بله"],["no","خیر"]],
 health_status: [["healthy","سالم"],["condition","دارای بیماری یا محدودیت"]],
 had_surgery: [["yes","بله"],["no","خیر"]],
 smokes: [["yes","بله"],["no","خیر"]],
 night_shift: [["yes","بله"],["no","خیر"]],
 travel_ready: [["yes","بله"],["no","خیر"]],
 has_insurance: [["yes","بله"],["no","خیر"]],
 military_status: [["completed","پایان خدمت"],["subject","مشمول"],["exempt","معاف"],["serving","در حال خدمت"]],
 marital_status: [["single","مجرد"],["married","متأهل"]],
};
const FIELDS = [
 ["مشخصات فردی", [["gender","جنسیت",true],["religion","دین",true],["denomination","مذهب",true],["birth_date","تاریخ تولد"],["marital_status","وضعیت تأهل"],["spouse_name","نام و نام خانوادگی همسر"],["nationality","ملیت"],["father_name","نام پدر"],["national_id","کد ملی"],["birth_certificate_number","شماره شناسنامه"],["birth_place","محل تولد"],["birth_certificate_city","محل صدور شناسنامه"],["city","شهر محل سکونت",true],["housing_type","وضعیت سکونت (شخصی / استیجاری / سایر)"],["address","آدرس محل سکونت"],["landline","تلفن ثابت"]]],
 ["شرایط همکاری", [["employment_type","نوع همکاری",true],["available_from","زمان آمادگی شروع به کار",true],["expected_salary","حقوق درخواستی (ریال)"],["night_shift","آمادگی شیفت شب"],["travel_ready","آمادگی مأموریت"],["referral_source","نحوه آشنایی با شرکت"],["referral_name","نام معرف (در صورت وجود)"]]],
 ["تحصیلات و مهارت‌ها", [["education","آخرین مدرک تحصیلی (در صورت نداشتن: فاقد مدرک)",true],["field_of_study","رشته تحصیلی"],["university","دانشگاه / مؤسسه"],["skills","مهارت‌ها و تخصص اصلی",true],["languages","زبان‌های خارجی"],["computer_skills","مهارت‌های کامپیوتری"]]],
 ["سوابق و بیمه", [["employed_now","اکنون شاغل هستید؟",true],["has_work_experience","سابقه کار دارید؟",true],["reason_for_leaving","علت تمایل به ترک کار"],["has_insurance","سابقه پرداخت حق بیمه"],["insurance_duration","مدت سابقه بیمه"],["insurance_number","شماره بیمه (اختیاری)"]]],
 ["وضعیت سلامت", [["health_status","وضعیت سلامت جسمانی",true],["health_details","شرح بیماری / محدودیت (در صورت تمایل)"],["had_surgery","سابقه عمل جراحی",true],["surgery_details","توضیح عمل جراحی (در صورت تمایل)"],["smokes","مصرف سیگار",true]]]
];
const REPEATABLE = [
 ["work_history","سوابق کاری",["company","نام سازمان / شرکت"],["position","سمت"],["start_date","تاریخ شروع"],["end_date","تاریخ پایان"],["duration","مدت سابقه"],["last_salary","آخرین حقوق"],["phone","تلفن شرکت"],["leaving_reason","علت ترک کار"]],
 ["education_history","سایر سوابق تحصیلی",["degree","مدرک"],["field","رشته"],["institution","مؤسسه"],["average","معدل"],["start_date","شروع"],["end_date","پایان"]],
 ["training_history","دوره‌های آموزشی",["title","عنوان دوره"],["institution","مؤسسه"],["duration","مدت"],["start_date","شروع"],["end_date","پایان"]],
 ["references","معرف‌ها",["full_name","نام و نام خانوادگی"],["relationship","نسبت / نوع آشنایی"],["address","نشانی"],["phone","تلفن"]],
 ["dependents","افراد تحت تکفل (اختیاری)",["full_name","نام و نام خانوادگی"],["gender","جنسیت"],["relationship","نسبت"],["birth_date","تاریخ تولد"],["education","تحصیلات"],["occupation","شغل"]]
];
export const careerFields = FIELDS;
export const careerRepeatable = REPEATABLE;

export default function CareersPage() {
 const [page,setPage] = useState(null), [basic,setBasic] = useState({full_name:"",mobile:"",requested_position:""}), [details,setDetails] = useState(EMPTY);
 const [website,setWebsite] = useState(""), [resume,setResume] = useState(null), [consent,setConsent] = useState(false), [busy,setBusy] = useState(false), [done,setDone] = useState(false), [error,setError] = useState("");
 useEffect(()=>{apiClient.get("/careers/page").then(r=>setPage(r.data)).catch(()=>setError("اطلاعات صفحه بارگذاری نشد."));},[]);
 const field = (name,label,required=false) => <TextField key={name} label={label} value={details[name]||""} required={required} select={!!OPTIONS[name]} onChange={e=>setDetails(p=>({...p,[name]:e.target.value}))} fullWidth size="small" multiline={/details|skills|reason_for_leaving|languages|computer_skills/.test(name)} minRows={/details|skills/.test(name)?2:undefined}>
 {OPTIONS[name]?.map(([val,txt])=><MenuItem key={val} value={val}>{txt}</MenuItem>)}
 </TextField>;
 const updateRow=(key,index,name,value)=>setDetails(p=>({...p,[key]:p[key].map((r,i)=>i===index?{...r,[name]:value}:r)}));
 async function submit(e) {e.preventDefault();setBusy(true);setError("");try {const body = new FormData(); body.append("data",JSON.stringify({...basic,details,consent,website})); if(resume) body.append("resume",resume); await apiClient.post("/careers/apply-with-resume",body,{timeout:45000});setDone(true);window.scrollTo({top:0,behavior:"smooth"});}catch(err){setError(err.response?.data?.detail||"خطا در ثبت درخواست. دوباره تلاش کنید.");}finally{setBusy(false);}}
 if(!page) return <Container maxWidth="md" sx={{py:8,textAlign:"center"}}>{error?<Alert severity="error">{error}</Alert>:<CircularProgress/>}</Container>;
 return <Box dir="rtl" sx={{minHeight:"100vh",bgcolor:"background.default",py:{xs:3,md:7}}}><Container maxWidth="md"><Stack spacing={3}>
 <Box><Typography variant="overline" color="primary">FAIPCO · فواد الیاف</Typography><Typography variant="h4" fontWeight={800}>{page.title}</Typography><Typography sx={{mt:2,whiteSpace:"pre-wrap"}}>{page.introduction}</Typography><Typography color="text.secondary" sx={{mt:1,whiteSpace:"pre-wrap"}}>{page.instructions}</Typography></Box>
 {done?<Alert severity="success">درخواست استخدام شما با موفقیت ثبت شد. از ثبت مجدد درخواست خودداری کنید.</Alert>:!page.is_open?<Alert severity="info">در حال حاضر ثبت درخواست استخدام غیرفعال است.</Alert>:<Box component="form" onSubmit={submit} autoComplete="off"><Stack spacing={2.5}>
 <input aria-hidden="true" tabIndex={-1} autoComplete="off" name="company_website" value={website} onChange={e=>setWebsite(e.target.value)} style={{position:"absolute",left:"-10000px",height:0,width:0,opacity:0}}/><Card><CardContent><Typography variant="h6" mb={2}>اطلاعات تماس و شغل درخواستی</Typography><Stack spacing={2}><TextField required label="نام و نام خانوادگی" value={basic.full_name} onChange={e=>setBasic(p=>({...p,full_name:e.target.value}))}/><TextField required label="شماره موبایل (09xxxxxxxxx)" inputProps={{pattern:"09[0-9]{9}"}} value={basic.mobile} onChange={e=>setBasic(p=>({...p,mobile:e.target.value}))}/><TextField required label="شغل درخواستی" value={basic.requested_position} onChange={e=>setBasic(p=>({...p,requested_position:e.target.value}))}/></Stack></CardContent></Card>
 {FIELDS.map(([title, fields])=><Card key={title}><CardContent><Typography variant="h6" mb={2}>{title}</Typography><Stack spacing={2}>{fields.map(([name,label,required])=>field(name,label,required))}{title==="مشخصات فردی"&&details.gender==="male"&&<>{field("military_status","وضعیت نظام وظیفه",true)}{details.military_status==="exempt"&&field("military_exemption_reason","علت معافیت",true)}</>}</Stack></CardContent></Card>)}
 {REPEATABLE.map(([key,label,...fields])=><Card key={key}><CardContent><Typography variant="h6">{label}</Typography><Typography variant="body2" color="text.secondary" mb={2}>در صورت نیاز ردیف‌های بیشتری اضافه کنید.</Typography><Stack spacing={2}>{details[key].map((row,i)=><Box key={i} sx={{p:2,border:"1px solid",borderColor:"divider",borderRadius:2}}><Stack spacing={1.5}>{fields.map(([name,title])=><TextField key={name} size="small" fullWidth label={title} required={key==="work_history"&&details.has_work_experience==="yes"&&["company","position"].includes(name)} value={row[name]||""} onChange={e=>updateRow(key,i,name,e.target.value)}/>)}<Button color="error" onClick={()=>setDetails(p=>({...p,[key]:p[key].filter((_,j)=>i!==j)}))}>حذف این ردیف</Button></Stack></Box>)}<Button disabled={details[key].length>=12} variant="outlined" onClick={()=>setDetails(p=>({...p,[key]:[...p[key],{}]}))}>افزودن {label}</Button></Stack></CardContent></Card>)}
 <Card><CardContent><Typography variant="h6" mb={2}>اطلاعات تکمیلی و تأیید</Typography><Stack spacing={2}><Button component="label" variant="outlined">{resume?`رزومه انتخاب‌شده: ${resume.name}`:"بارگذاری رزومه PDF (اختیاری، حداکثر ۳ مگابایت)"}<input type="file" hidden accept="application/pdf,.pdf" onChange={e=>{const file=e.target.files?.[0];if(file?.size>3*1024*1024){setError("حجم رزومه نباید بیش از ۳ مگابایت باشد.");setResume(null);}else{setResume(file||null);setError("");}}}/></Button><TextField label="ویژگی مثبت" value={details.positive_trait||""} onChange={e=>setDetails(p=>({...p,positive_trait:e.target.value}))}/><TextField label="ویژگی قابل بهبود" value={details.negative_trait||""} onChange={e=>setDetails(p=>({...p,negative_trait:e.target.value}))}/><TextField label="آشنای شاغل در فواد الیاف" value={details.internal_contact||""} onChange={e=>setDetails(p=>({...p,internal_contact:e.target.value}))}/><TextField multiline minRows={2} label="توضیحات تکمیلی" value={details.extra_notes||""} onChange={e=>setDetails(p=>({...p,extra_notes:e.target.value}))}/><FormControlLabel control={<Checkbox checked={details.accuracy_confirmed} onChange={e=>setDetails(p=>({...p,accuracy_confirmed:e.target.checked}))} required/>} label="صحت اطلاعات واردشده را تأیید می‌کنم."/><FormControlLabel control={<Checkbox checked={consent} onChange={e=>setConsent(e.target.checked)} required/>} label="با بررسی و نگهداری اطلاعاتم، از جمله داده‌های حساس ارائه‌شده، برای فرایند جذب موافقم و می‌دانم ثبت فرم تعهدی برای استخدام ایجاد نمی‌کند."/></Stack></CardContent></Card>
 {error&&<Alert severity="error">{String(error)}</Alert>}<Button disabled={busy} size="large" type="submit" variant="contained">{busy?"در حال ثبت...":"ثبت درخواست استخدام"}</Button>
 </Stack></Box>}
 <Divider/><Typography align="center" variant="caption" color="text.secondary">فواد الیاف · FAIPCO</Typography></Stack></Container></Box>;
}
