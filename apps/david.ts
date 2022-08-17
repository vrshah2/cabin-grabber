import axios from 'axios';
import dayjs from 'dayjs';
import sgMail from '@sendgrid/mail';
import twilio from 'twilio';
import dotenv from 'dotenv';
import { db } from '../../models';
dotenv.config();

sgMail.setApiKey(process.env.SENDGRID_API_KEY!);

type DateAvailability = {
  date: dayjs.Dayjs;
  availabilty: boolean;
};
type DateSummary = {
  availabilities: dayjs.Dayjs[];
  id: number;
  name: string;
};
type Cabin = {
  name: string;
  id: string;
  startDate: dayjs.Dayjs;
  endDate: dayjs.Dayjs;
  range?: number;
  preferredStartDDD?: ('Sun' | 'Mon' | 'Tue' | 'Wed' | 'Thur' | 'Fri' | 'Sat')[];
  subIds?: string[];
  phone?: string[];
};

export const getLocationAvailability = async (
  locationId: string,
  startDate: dayjs.Dayjs,
  toDate: dayjs.Dayjs,
  selectedIds: string[] = []
) => {
  const response = await axios.get(`https://ws.visbook.com/8/api/${locationId}/webproducts`);

  let ids = response.data.map((el: { webProductId: number; unitName: string }) => ({
    id: el.webProductId,
    name: el.unitName,
  }));

  if (selectedIds.length !== 0) {
    ids = ids.filter(({ id }: { id: any }) => selectedIds.includes(`${id}`));
  }

  const months: number[] = [];

  for (let month = startDate.month(); month < toDate.month(); month += 1) {
    months.push(month + 1);
  }

  const summary: DateSummary[] = [];

  for (const { id, name } of ids) {
    const availabilities = await Promise.all(
      months.map(async (month) => {
        const availability = await axios.get(
          `https://ws.visbook.com/8/api/${locationId}/availability/${id}/${toDate.format(
            'YYYY'
          )}-${month}`
        );
        const allDays: DateAvailability[] = availability.data.items.map((el: any) => ({
          date: dayjs(el.date),
          availability: el.webProducts[0]?.availability?.available || false,
        }));

        const availableDays = allDays.filter((el: any) => el.availability === true);

        console.log(
          `checking ${locationId} - ${name}(${id}) - Month ${month}: ${availableDays.length} / ${allDays.length} available`
        );
        return availableDays;
      })
    );

    summary.push({
      availabilities: availabilities.reduce((prev: dayjs.Dayjs[], current: DateAvailability[]) => {
        return prev.concat(current.map((el: DateAvailability) => el.date));
      }, []),
      id: id,
      name: name,
    });
  }

  return summary;
};

export const fetchDataForCabins = async (cabins: Cabin[], email = 'david.lky.123@gmail.com') => {
  for (const cabin of cabins) {
    const { name, id, startDate, endDate, range = 1, preferredStartDDD = [], subIds = [] } = cabin;
    try {
      const availabilities: DateSummary[] = await getLocationAvailability(
        id,
        startDate,
        endDate,
        subIds
      );

      let html = '';
      for (const availability of availabilities) {
        // get diff
        const currentAvailability = await db.HytteLog.findAll({
          where: {
            hytteId: `${availability.id}`,
          },
        });

        const availabilityStringSet = new Set<string>(
          availability.availabilities.map((el) => el.format('YYYY-MM-DD'))
        );
        const pastAvailabilitySet = new Set<string>();

        currentAvailability
          .map((el: any) => el.availableDate)
          .forEach((date: string) => {
            if (!availabilityStringSet.delete(date)) {
              pastAvailabilitySet.add(date);
            }
          });

        if (pastAvailabilitySet.size !== 0 || availabilityStringSet.size !== 0) {
          let availabilityHtml = '';
          if (pastAvailabilitySet.size !== 0) {
            const dates = Array.from(pastAvailabilitySet);
            availabilityHtml += `<p>Booked</p><ul>`;
            availabilityHtml += dates
              .map((date) => dayjs(date).format('YYYY-MM-DD ddd'))
              .map((el) => `<li>${el}</li>`)
              .join('');
            availabilityHtml += `</ul>`;

            await db.HytteLog.destroy({
              where: {
                hytteId: `${availability.id}`,
                availableDate: dates,
              },
            });
          }
          if (availabilityStringSet.size !== 0) {
            const dates = [...availability.availabilities];
            dates.sort((a, b) => (a.isAfter(b) ? 1 : -1));
            const dateRanges = dates.reduce((prev, el) => {
              // has preferred date
              let hasPreferredDate =
                preferredStartDDD.length === 0 ||
                (preferredStartDDD as string[]).includes(el.format('ddd'));

              const latestRange = prev[prev.length - 1];
              if (
                latestRange &&
                el.format('YYYY-MM-DD') ===
                  latestRange.date.add(latestRange.range, 'day').format('YYYY-MM-DD')
              ) {
                prev[prev.length - 1].range += 1;
                prev[prev.length - 1].hasPreferredDate =
                  prev[prev.length - 1].hasPreferredDate || hasPreferredDate;
                return prev;
              } else {
                return prev.concat({ date: el, range: 1, hasPreferredDate });
              }
            }, [] as { date: dayjs.Dayjs; range: number; hasPreferredDate: boolean }[]);

            const validRanges = dateRanges.filter((el) => el.range >= range && el.hasPreferredDate);
            if (validRanges.length > 0) {
              availabilityHtml += `<p>Bookable</p><ul>`;
              availabilityHtml += validRanges
                .map(
                  (range) => `${dayjs(range.date).format('YYYY-MM-DD ddd')} - ${range.range} Day(s)`
                )
                .map((el) => `<li>${el}</li>`)
                .join('');
              availabilityHtml += `</ul>`;
            }

            await db.HytteLog.bulkCreate(
              Array.from(availabilityStringSet).map((date) => ({
                hytteId: `${availability.id}`,
                availableDate: date,
              }))
            );
          }
          if (availabilityHtml.length > 0) {
            html += `<p>${availability.name}</p>\n${availabilityHtml}`;
          }
        }
      }

      if (html.length > 0) {
        console.log(`emailing for ${name} - ${id}`);
        await sgMail.send({
          to: email, // Change to your recipient
          from: 'no-reply@mapper.world', // Change to your verified sender
          subject: `Hytta Update - ${name}`,
          html,
        });
        console.log(`done emailing for ${name} - ${id}`);
      }
    } catch (e) {
      console.log(e);
      // await sgMail.send({
      //   to: email, // Change to your recipient
      //   from: 'no-reply@mapper.world', // Change to your verified sender
      //   subject: `[Failed]Hytta Update - ${name}`,
      //   html: `<pre>${JSON.stringify(e, null, 2)}</pre>`,
      // });
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
};

const cabins: Cabin[] = [
  {
    name: 'Flokehyttene',
    id: '6446',
    startDate: dayjs('2021-05-01'),
    endDate: dayjs('2021-10-01'),
    range: 1,
    phone: ['+16478369673', '+4791398730'],
  },
  {
    name: 'Runde',
    id: '6761',
    startDate: dayjs('2021-05-01'),
    endDate: dayjs('2021-09-01'),
    range: 2,
  },
  {
    name: 'Skapet (Lysefjord)',
    id: '5528',
    startDate: dayjs('2021-04-01'),
    endDate: dayjs('2021-08-01'),
    preferredStartDDD: ['Fri', 'Sat'],
    subIds: ['88687', '88689', '88692'],
  },
  {
    name: 'Kaldhusetter (Geiranger)',
    id: '6760',
    startDate: dayjs('2021-06-01'),
    endDate: dayjs('2021-08-01'),
    preferredStartDDD: ['Fri', 'Sat'],
  },
  {
    name: 'Skala (Geiranger)',
    id: '5493',
    startDate: dayjs('2021-06-01'),
    endDate: dayjs('2021-08-01'),
    subIds: ['104232', '104233', '104234', '104235'],
    preferredStartDDD: ['Fri', 'Sat'],
  },
  {
    name: 'Oslo Fuglhytte',
    id: '6516',
    startDate: dayjs('2021-04-03'),
    endDate: dayjs('2021-09-04'),
    preferredStartDDD: ['Fri', 'Sat'],
  },
];

fetchDataForCabins(cabins);

const sendSms = (message: string, number: string) => {
  const accountSid = process.env.TWILIO_ACCOUNT_SID;
  const authToken = process.env.TWILIO_AUTH_TOKEN;
  const client = twilio(accountSid, authToken);

  client.messages
    .create({
      body: message,
      from: '+17047654772',
      to: number,
    })
    .then((message) => console.log(message.sid));
};